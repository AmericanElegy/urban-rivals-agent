"""Local OCR of a cropped Unity canvas. No game API or cloud model is used."""
from dataclasses import dataclass
from pathlib import Path
import json
import re
import uuid
import time
import unicodedata
from .engine import Card, Move, Player, State, parse_effect, resolve
from .solver import advise
from .star_catalog import StarCatalog
from .mode_policy import recommend_move, VALID_MODES


def normalize(text):
    text=unicodedata.normalize("NFKD",text.casefold())
    return re.sub(r"[^a-z0-9]", "", text)


class RecognitionError(ValueError):
    pass


class LocalOCR:
    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR
        self.model = RapidOCR(det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False, intra_op_num_threads=2, inter_op_num_threads=1, det_limit_type="min", det_limit_side_len=192)

    def text(self, image, box, minimum=.85, first_line=False, detail=False):
        import numpy as np
        from PIL import ImageOps
        w,h = image.size
        x1,y1,x2,y2 = box
        crop = image.crop((int(x1*w),int(y1*h),int(x2*w),int(y2*h)))
        if crop.width>900:
            crop = crop.resize((crop.width//2,crop.height//2))
        else:
            scale=1 if crop.width>=300 else 2
            if scale>1:
                crop = crop.resize((crop.width*scale,crop.height*scale))
        crop = ImageOps.expand(crop, border=12, fill="black")
        result, _ = self.detect(np.array(crop)[:,:,::-1].copy(),detail)
        if not result:
            return ""
        items=[item for item in result if float(item[2])>=minimum]
        if first_line and items:
            items.sort(key=lambda item: min(point[1] for point in item[0]))
            top=min(point[1] for point in items[0][0])
            height=max(point[1] for point in items[0][0])-top
            items=[item for item in items if min(point[1] for point in item[0])<top+height*.6]
            items.sort(key=lambda item: min(point[0] for point in item[0]))
        return " ".join(item[1] for item in items)

    def locate(self, image, box, minimum=.8):
        """Return [(text, score, cx, cy)] with centers normalized to the image.

        Uses the same crop/scale/padding as text(), then maps each detected
        quadrilateral back to full-canvas coordinates so callers can click it.
        """
        import numpy as np
        from PIL import ImageOps
        w,h=image.size
        x1,y1,x2,y2=box
        left,top=int(x1*w),int(y1*h)
        crop=image.crop((left,top,int(x2*w),int(y2*h)))
        factor=1.0
        if crop.width>900:
            factor=.5
        elif crop.width<300:
            factor=2.0
        if factor!=1.0:
            crop=crop.resize((max(1,int(crop.width*factor)),max(1,int(crop.height*factor))))
        pad=12
        crop=ImageOps.expand(crop,border=pad,fill="black")
        result,_=self.detect(np.array(crop)[:,:,::-1].copy(),True)
        found=[]
        for points,text,score in result or ():
            if float(score)<minimum:
                continue
            cx=sum(p[0] for p in points)/len(points)
            cy=sum(p[1] for p in points)/len(points)
            found.append((text,float(score),
                          (left+(cx-pad)/factor)/w,(top+(cy-pad)/factor)/h))
        return found

    def detect(self,pixels,detail=False):
        """Restore shared detector settings even when inference fails."""
        detector=self.model.text_det
        previous=detector.limit_side_len
        prev_type=getattr(detector,"limit_type",None)
        try:
            if detail:
                detector.limit_side_len=736
                if prev_type is not None:
                    detector.limit_type="max"
            elif prev_type is not None and pixels is not None and pixels.shape[1]>=300:
                detector.limit_type="max"
                detector.limit_side_len=736
            else:
                detector.limit_side_len=192
            return self.model(pixels)
        finally:
            detector.limit_side_len=previous
            if prev_type is not None:
                detector.limit_type=prev_type

    def precise_text(self,image,box,minimum=.85):
        return self.text(image,box,minimum,detail=True)

    def title(self,image,box,minimum=.8):
        return self.text(image,box,minimum,first_line=True)

    def number(self,image,box,palette="white"):
        import cv2
        import numpy as np
        from PIL import Image
        w,h=image.size
        x1,y1,x2,y2=box
        crop=image.crop((int(x1*w),int(y1*h),int(x2*w),int(y2*h))).convert("RGB")
        # Stats use white digits over colored icons. Remove those colored icons
        # before OCR rather than accepting a low-confidence guess at a digit.
        pixels=np.array(crop)
        if palette not in ("white","attack","damage"):
            raise ValueError("Unknown numeric palette")
        r,g,b=pixels.astype("float32").transpose(2,0,1)
        from PIL import ImageOps
        readings=[]
        self.last_number_evidence=readings
        masks=[]
        for threshold in (145,160,175,190,205):
            if palette=="attack":
                ink=(b>threshold)&(b>r*1.2)&(g<b*.65)&(r>g*1.2)
            elif palette=="damage":
                ink=(r>threshold)&(g<r*.65)&(b>50)&(b<r*.8)
            else:
                ink=pixels.min(axis=2)>threshold
            white=ink.astype("uint8")*255
            count,labels,stats,_=cv2.connectedComponentsWithStats(white)
            clean=np.zeros_like(white)
            height,width=white.shape
            components=[]
            for i in range(1,count):
                x,y,cw,ch,area=stats[i]
                if (area<6 or ch<height*.22 or ch>height*.90 or cw>width*.8
                        or x==0 or y==0 or x+cw>=width or y+ch>=height
                        or cw/ch<.15):
                    continue
                components.append((i,ch,area))
            if not components:
                continue
            tallest=max(ch for _,ch,_ in components)
            largest=max(area for _,ch,area in components if ch>=tallest*.75)
            for i,ch,area in components:
                if ch>=tallest*.75 and area>=largest*.25:
                    clean[labels==i]=255
            points=cv2.findNonZero(clean)
            if points is None:
                continue
            x,y,cw,ch=cv2.boundingRect(points)
            monochrome=ImageOps.expand(Image.fromarray(clean[y:y+ch,x:x+cw]).convert("RGB"),border=6,fill="black")
            masks.append(monochrome)
            result,_=self.model(np.array(monochrome),use_det=False,use_cls=False,use_rec=True)
            if result and re.fullmatch(r"\d{1,3}",result[0][0]):
                readings.append((result[0][0],float(result[0][1])))
            value=numeric_consensus(readings)
            if value:
                return value
        # Very narrow glyphs need different context around their strokes.
        # Vary padding with the same confidence/consensus requirements.
        for monochrome in masks:
            glyph=monochrome.crop((6,6,monochrome.width-6,monochrome.height-6))
            for border in (2,4,1,8,12):
                variant=ImageOps.expand(glyph,border=border,fill="black")
                result,_=self.model(np.array(variant),use_det=False,use_cls=False,use_rec=True)
                if result and re.fullmatch(r"\d{1,3}",result[0][0]):
                    readings.append((result[0][0],float(result[0][1])))
                value=numeric_consensus(readings)
                if value:
                    return value
        for monochrome in masks:
            detected=self.precise_text(monochrome,(0,0,1,1),.95)
            if re.fullmatch(r"\d{1,3}",detected):
                readings.append((detected,.95))
            value=numeric_consensus(readings)
            if value:
                return value
        return ""

    def counter(self,image,box):
        # The multiplier sign can touch the first digit after video resampling.
        # Black padding keeps that clipped sign fragment from discarding the
        # entire digit component. It does not change recognition thresholds.
        from PIL import ImageOps
        w,h=image.size
        x1,y1,x2,y2=box
        # Inputs are canonical 1318x744 boards. Resampling can leave a connected
        # sign fragment; a failed primary crop needs two agreeing tighter crops.
        readings=[]
        for trim in (2,3,4):
            crop=image.crop((int(x1*w)+trim,int(y1*h),int(x2*w),int(y2*h)))
            value=self.number(ImageOps.expand(crop,3,"black"),(0,0,1,1))
            if trim==2 and value:
                return value
            if trim!=2:
                readings.append(value)
        return readings[0] if readings[0] and readings[0]==readings[1] else ""


def numeric_consensus(readings):
    """Two agreeing reads, including a high-score read; conflicts abstain.

    OCR scores are model scores, not calibrated probabilities of correctness.
    """
    high={text for text,score in readings if score>=.95}
    if len(high)!=1:
        return ""
    value=next(iter(high))
    return value if sum(text==value and score>=.85 for text,score in readings)>=2 else ""


def parse_timer(text):
    """Accept only the isolated training move clock, at most 2:59."""
    match=re.fullmatch(r"\s*(0?[0-2]):([0-5]\d)\s*",text)
    return int(match[1])*60+int(match[2]) if match else None


class Catalog:
    def __init__(self, path=None, allow_star_fallback=False):
        path = Path(path) if path else Path(__file__).parent / "data" / "training_cards.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "urban-rivals/cards/v1":
            raise ValueError("Unknown catalog schema")
        self.entries = {}
        self.evolutions = {}
        self.allow_star_fallback = allow_star_fallback
        self.star_catalog = StarCatalog() if (allow_star_fallback and path.name == "training_cards.json") else None
        for raw in data["cards"]:
            raw = dict(raw)
            day_only = raw.pop("day_only",False)
            for field in ("ability","bonus"):
                raw[field] = parse_effect(raw.get(field,""))
            card = Card(**raw)
            key = normalize(card.name)
            identity=(key,card.power,card.damage,card.stars)
            if identity in self.evolutions:
                raise ValueError("Duplicate or conflicting catalog evolution")
            self.evolutions[identity]=(card,day_only)
            # Existing manifests name a documented reference evolution. Live
            # recognition always passes observed stats to select an exact level.
            self.entries.setdefault(key,(card,day_only))

    def identify(self,text,day,stats=None):
        key=normalize(text)
        matches=([self.evolutions[(key,*stats)]] if (key,*stats) in self.evolutions else []) if stats is not None else [entry for name,entry in self.entries.items() if key==name]
        if len(matches) != 1:
            if self.star_catalog is not None:
                p, d, s = stats if stats is not None else (None, None, None)
                evo = self.star_catalog.resolve(text, stars=s, power=p, damage=d)
                if evo is not None:
                    return evo.card
                if p is not None and d is not None and text.strip():
                    return Card(name=text.strip(), power=p, damage=d, stars=s or 1, clan="Unknown")
            from .reference_database import lookup_reference
            reference=lookup_reference(text)
            if reference["official_maximum_levels"]:
                raise RecognitionError(f"Known reference card {text!r}, observed stats {stats}: this evolution/mechanic is not validated for live execution; use the reference command for source facts")
            raise RecognitionError(f"Unknown or ambiguous card name: {text!r}; add its verified evolution to the catalog")
        card, day_only = matches[0]
        if day_only and day is not True:
            raise RecognitionError(f"{card.name}: only the observed Day bonus is cataloged")
        return card


# Reference stake-panel click centers measured on a 1318x744 canvas at
# hud_scale 1.0. Live layouts shift with browser size, so these are only the
# last resort; text located on the current frame always wins.
STAKE_TEXT_DEFAULTS={"min":(.578,.513),"max":(.874,.513),"confirm":(.722,.675)}
STAKE_ICON_DEFAULTS={"plus":(.874,.442)}
STAKE_SEARCH_BOX=(.45,.30,1.0,.80)
CALIBRATION_KEYS={"plus":"pillz_plus","minus":"pillz_minus","fury":"fury_btn","confirm":"confirm_btn"}


def _stake_label(text):
    norm=normalize(text)
    if norm in ("min","max"):
        return norm
    if norm.startswith("confirm"):
        return "confirm"
    if "fury" in norm and len(norm)<=12:
        return "fury"
    return None


def _fit_axis(pairs):
    """Least-squares a*default+b from (default, observed) pairs.

    One anchor, or anchors sharing a default coordinate, give translation only.
    An implausible scale also falls back to translation.
    """
    if not pairs:
        return 1.0,0.0
    defaults=[d for d,_ in pairs]
    observed=[o for _,o in pairs]
    md=sum(defaults)/len(defaults)
    mo=sum(observed)/len(observed)
    spread=sum((d-md)**2 for d in defaults)
    if spread>1e-6:
        a=sum((d-md)*(o-mo) for d,o in pairs)/spread
        if .5<=a<=1.5:
            return a,mo-a*md
    return 1.0,mo-md


def stake_layout(found,calibration=None):
    """Choose click targets for the open stake panel.

    found: [(text, score, cx, cy)] from LocalOCR.locate on the current frame.
    Priority per target: text located now > saved calibration > the reference
    layout moved by the offset/scale measured from whichever anchors were found.
    Returns {target: (x, y)} plus "_source": {target: "text"|"calibration"|"layout"|"default"}.
    """
    hits={}
    ambiguous=set()
    for text,score,cx,cy in found:
        label=_stake_label(text)
        if label is None:
            continue
        if label in hits:
            ambiguous.add(label)
        hits[label]=(cx,cy)
    for label in ambiguous:
        hits.pop(label,None)
    anchors=[(STAKE_TEXT_DEFAULTS[k],hits[k]) for k in STAKE_TEXT_DEFAULTS if k in hits]
    ax,bx=_fit_axis([(d[0],o[0]) for d,o in anchors])
    ay,by=_fit_axis([(d[1],o[1]) for d,o in anchors])
    moved="layout" if anchors else "default"
    def project(point):
        return (min(1.0,max(0.0,ax*point[0]+bx)),min(1.0,max(0.0,ay*point[1]+by)))
    layout={}
    source={}
    for key,point in {**STAKE_TEXT_DEFAULTS,**STAKE_ICON_DEFAULTS,"fury":None,"minus":None}.items():
        cal_key=CALIBRATION_KEYS.get(key)
        if key in hits:
            layout[key],source[key]=hits[key],"text"
        elif calibration and cal_key in calibration:
            pt=calibration[cal_key]
            layout[key],source[key]=(float(pt["x"]),float(pt["y"])),"calibration"
        elif point is not None:
            layout[key],source[key]=project(point),moved
    layout["_source"]=source
    return layout


@dataclass(frozen=True)
class Board:
    state: State
    observed_card: int | None
    seconds_left: int
    spent: tuple[tuple[int | None, ...], ...]


class CanvasReader:
    CENTERS=(.221,.406,.591,.776)
    PANEL_ATTACK=(.55,.55,.635,.64)
    PANEL_DAMAGE=(.74,.55,.815,.64)
    RESOURCE_BOXES=(
        ("our_life",(.76,.90,.81,.99),"right","bottom"),
        ("opponent_life",(.22,0,.275,.08),"left","top"),
        ("our_pillz",(.68,.90,.735,.99),"right","bottom"),
        ("opponent_pillz",(.30,0,.35,.08),"left","top"))

    def set_canvas_css_width(self,width):
        import math
        if type(width) not in (int,float) or not math.isfinite(width) or not 640<=width<=4096:
            raise RecognitionError("Uncalibrated canvas CSS width")
        self.hud_scale=1318/width

    def hud_box(self,box,x_anchor="center",y_anchor="center"):
        scale=getattr(self,"hud_scale",1.0)
        anchors={"left":0,"top":0,"center":.5,"right":1,"bottom":1}
        ax,ay=anchors[x_anchor],anchors[y_anchor]
        x1,y1,x2,y2=box
        return (ax+(x1-ax)*scale,ay+(y1-ay)*scale,
                ax+(x2-ax)*scale,ay+(y2-ay)*scale)

    def turn_seconds(self,image):
        box=(.64,.46,.73,.54)
        seconds=parse_timer(self.precise_text(image,self.hud_box(box),.8))
        if seconds is None and getattr(self,"hud_scale",1.0)!=1.0:
            # Unity can retain its reference HUD after the browser is resized.
            # Select that observed layout only from a complete timer. All card,
            # resource and receipt checks still run before an action is allowed.
            reference=parse_timer(self.precise_text(image,box,.8))
            if reference is not None:
                self.hud_scale=1.0
                return reference
        if seconds is None:
            wider=parse_timer(self.precise_text(image,(.60,.46,.74,.55),.8))
            if wider is not None:
                if getattr(self,"hud_scale",1.0)!=1.0:
                    self.hud_scale=1.0
                return wider
        return seconds

    # Center x of our cyan life heart at hud_scale 1 with the plain bottom bar.
    # Measured on a live round-4 frame where a HEAL button pushed the bar left.
    OUR_HEART_X=.758

    @staticmethod
    def find_our_heart(image):
        """Locate the cyan life heart in the bottom HUD; (cx, cy) or None."""
        import cv2
        import numpy as np
        w,h=image.size
        top=int(.88*h)
        strip=np.array(image.crop((0,top,w,h)).convert("RGB")).astype("int16")
        r,g,b=strip[...,0],strip[...,1],strip[...,2]
        mask=((r<190)&(g>200)&(b>200)&(g-r>50)).astype("uint8")
        count,_,stats,centers=cv2.connectedComponentsWithStats(mask)
        best=None
        for i in range(1,count):
            x,y,cw,ch,area=stats[i]
            if not (.012*h<=ch<=.04*h and .6<=cw/ch<=1.6 and area>=.4*cw*ch):
                continue
            if best is None or area>best[0]:
                best=(area,(centers[i][0]/w,(centers[i][1]+top)/h))
        return best[1] if best else None

    def bottom_bar_shift(self,image):
        """Horizontal shift of our bottom resource bar (e.g. a HEAL button)."""
        try:
            heart=self.find_our_heart(image)
        except Exception:
            return 0.0
        if heart is None:
            return 0.0
        scale=getattr(self,"hud_scale",1.0)
        reference=1+(self.OUR_HEART_X-1)*scale
        dx=heart[0]-reference
        return dx if abs(dx)>=.01 else 0.0

    def read_resources(self,image):
        resources={}
        shift=self.bottom_bar_shift(image) if image is not None else 0.0
        for name,box,ax,ay in self.RESOURCE_BOXES:
            target=self.hud_box(box,ax,ay)
            if shift and name.startswith("our_"):
                target=(target[0]+shift,target[1],target[2]+shift,target[3])
            try:
                resources[name]=self.number(image,target)
            except RecognitionError as error:
                if hasattr(self.ocr,"counter"):
                    try:
                        resources[name]=self.number(image,target,kind="counter")
                        continue
                    except RecognitionError:
                        pass
                raise RecognitionError(f"{name}: {error}") from error
        return resources

    def __init__(self,ocr=None,catalog=None):
        self.ocr=ocr or LocalOCR()
        self.catalog=catalog or Catalog()
        self.initial_hand=None

    def text(self,image,box,minimum=.85):
        return self.ocr.text(image,box,minimum)

    def stake_text(self,image):
        """Located stake-panel words for this frame (cached per image)."""
        cached=getattr(self,"_stake_cache",None)
        if cached and cached[0] is image:
            return cached[1]
        locate=getattr(self.ocr,"locate",None)
        found=locate(image,STAKE_SEARCH_BOX,.8) if locate else []
        self._stake_cache=(image,found)
        return found

    def stake_open(self,image):
        return any(_stake_label(text)=="confirm" for text,*_ in self.stake_text(image))

    def stake_targets(self,image,calibration=None):
        return stake_layout(self.stake_text(image),calibration)

    def round_scene(self,image):
        """A phase hint only: board() must still verify the complete state."""
        banner=self.text(image,(.27,.46,.73,.55),.8)
        self._last_banner=(id(image),banner)
        return bool(re.search(r"ROUND\s*[1-4]\s*[/|]\s*4",banner,re.I)
                    and "yourturn" in normalize(banner))

    def title(self,image,box,minimum=.8):
        return self.ocr.title(image,box,minimum) if hasattr(self.ocr,"title") else self.text(image,box,minimum)

    def precise_text(self,image,box,minimum=.85):
        return self.ocr.precise_text(image,box,minimum) if hasattr(self.ocr,"precise_text") else self.text(image,box,minimum)

    def card_name(self,image,x,y,side,minimum=.8):
        if side==1:
            raised=self.raised_title(image,x,minimum)
            if raised:
                return raised
        return self.title(image,(x-.055,y-.02,x+.065,y+.08),minimum)

    def raised_title(self,image,x,minimum=.8):
        if not self.raised_marker(image,x):
            return ""
        raised=self.precise_text(image,(x-.025,.075,x+.085,.115),minimum)
        return raised if len(re.sub(r"[^a-z]","",normalize(raised)))>=3 else ""

    @staticmethod
    def raised_marker(image,x):
        """Find the white/silver selection disc, not letters in scenery above a card."""
        import cv2
        import numpy as np
        w,h=image.size
        left,top=int((x-.08)*w),int(.045*h)
        pixels=np.array(image.convert("RGB"))[top:int(.115*h),left:int((x-.04)*w)]
        white=((pixels.min(axis=2)>195)*255).astype("uint8")
        contours,_=cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area=cv2.contourArea(contour)
            perimeter=cv2.arcLength(contour,True)
            bx,by,bw,bh=cv2.boundingRect(contour)
            if (70<=area<=650 and .65<=bw/bh<=1.5 and perimeter
                    and 4*3.14159*area/(perimeter*perimeter)>.60
                    and top+by+bh/2 < .11*h):
                return True
        mx=pixels.max(axis=2).astype("int16")
        mn=pixels.min(axis=2).astype("int16")
        pill=(((mn>155)&((mx-mn)<35))*255).astype("uint8")
        pill=cv2.morphologyEx(pill,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        contours,_=cv2.findContours(pill,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            hull=cv2.convexHull(contour)
            area=cv2.contourArea(contour)
            hull_area=cv2.contourArea(hull)
            hull_per=cv2.arcLength(hull,True)
            bx,by,bw,bh=cv2.boundingRect(contour)
            if (140<=area<=900 and .65<=bw/bh<=1.5 and hull_per
                    and 4*3.14159*hull_area/(hull_per*hull_per)>.65
                    and top+by+bh/2 < .11*h):
                return True
        return False

    @staticmethod
    def played_marker(image,x,side):
        import numpy as np
        w,h=image.size
        y=.695 if side==0 else .245
        p=np.array(image.convert("RGB"))[int((y+.006)*h):int((y+.045)*h),int((x-.025)*w):int((x+.005)*w)]
        r,g,b=[p[:,:,i].astype("int16") for i in range(3)]
        purple=(r>80)&(b>100)&(g<r*.7)&(g<b*.7)
        yellow=(r>170)&(g>140)&(b<120)
        star_y=.785 if side==0 else .335
        stars=np.array(image.convert("RGB"))[int((star_y-.012)*h):int((star_y+.012)*h),int((x-.05)*w):int((x+.05)*w)].astype("int16")
        sr,sg,sb=[stars[:,:,i] for i in range(3)]
        bright_stars=(sr>200)&(sg>120)&(sb<sg*.55)
        return bool(purple.sum()>=6 and yellow.sum()>=4 and bright_stars.sum()<3)

    def played_pillz(self,image,x,side):
        """Read only verified dimmed-card markers, including the free pill."""
        if not self.played_marker(image,x,side):
            return None
        y=.695 if side==0 else .245
        count=None
        if hasattr(self,"ocr") and hasattr(self.ocr,"text"):
            raw=self.text(image,(x-.005,y,x+.05,y+.06),.75)
            match=re.search(r"[x×]\s*(\d{1,2})\b",raw,re.I)
            if match:
                count=int(match[1])
        if count is None:
            count=self.number(image,(x+.007,y+.003,x+.04,y+.052),kind="counter")
        if not 1<=count<=99:
            raise RecognitionError("Played pill multiplier is outside the supported range")
        return count-1

    @staticmethod
    def stat_box(x,y,damage=False):
        return (x-.075,y+(.035 if damage else -.045),x-.025,y+(.09 if damage else .03))

    def number(self,image,box,kind="number"):
        if kind in ("attack","damage"):
            text=self.ocr.number(image,box,palette=kind)
        elif kind=="counter" and hasattr(self.ocr,"counter"):
            text=self.ocr.counter(image,box)
        else:
            text=self.ocr.number(image,box) if hasattr(self.ocr,"number") else self.text(image,box)
        if not re.fullmatch(r"\s*\d{1,3}\s*",text):
            raise RecognitionError(f"Resource or attack count is unreadable: {text!r}")
        return int(text)

    def panel_number(self,image,box,kind):
        return self.number(image,box,kind)

    def stars(self,image,x,y):
        import numpy as np
        pixels=np.array(image.convert("RGB"))
        h,w,_=pixels.shape
        x1,x2=int((x-.05)*w),int((x+.05)*w)
        best=None
        for dy in (.004,0.0,-.005):
            sy=y+dy
            strip=pixels[int((sy-.006)*h):int((sy+.006)*h),x1:x2]
            if strip.size==0 or (strip.max(axis=2)<95).mean()<.35:
                continue
            mask=(strip[:,:,0]>180)&(strip[:,:,1]>140)&(strip[:,:,2]<90)
            occupied=(mask.sum(axis=0)>=3).tolist()
            runs=[]
            current=0
            for value in occupied+[False]:
                if value:
                    current+=1
                elif current:
                    if 3<=current<=14:
                        runs.append(current)
                    current=0
            if 1<=len(runs)<=5:
                score=(int(mask.sum()),len(runs),-abs(dy))
                if best is None or score>best[0]:
                    best=(score,len(runs))
        if best is not None:
            return best[1]
        strip=pixels[int((y-.012)*h):int((y+.012)*h),x1:x2]
        mask=(strip[:,:,0]>170)&(strip[:,:,1]>120)&(strip[:,:,2]<100)
        occupied=(mask.sum(axis=0)>=3).tolist()
        runs=[]
        current=0
        for value in occupied+[False]:
            if value:
                current+=1
            elif current:
                if current>=3:
                    runs.append(current)
                current=0
        if not 1 <= len(runs) <= 5:
            raise RecognitionError("Evolution stars could not be counted")
        return len(runs)

    def day(self,image):
        import numpy as np
        w,h=image.size
        x1,y1,x2,y2=self.hud_box((.79,0,.825,.08),"right","top")
        p=np.array(image.crop((int(w*x1),int(h*y1),int(w*x2),int(h*y2))).convert("RGB"))
        yellow=(p[:,:,0]>180)&(p[:,:,1]>140)&(p[:,:,2]<90)
        return True if yellow.sum()>20 else None

    def diagnostics(self,image):
        """Read every crop independently. Never click, require a timer, or stop at
        the first unknown name. Useful on a saved board long after a match ends.
        """
        banner=self.text(image,(.27,.46,.73,.55),.7)
        report={"phase":"round_board","banner":banner,"day":None,"cards":[]}
        if not re.search(r"ROUND\s*[1-4]\s*[/|]\s*4",banner,re.I):
            screen=self.text(image,(0,0,1,1),.7)
            text=normalize(screen)
            report["phase"]=("stake_panel" if "confirmthestake" in text else
                             "match_result" if "playagain" in text and ("victory" in text or "defeat" in text) else
                             "training_menu" if "training" in text and "play" in text else "not_round_board")
            report["screen_text"]=screen
            return report
        report["day"]=self.day(image)
        report["round"]=int(re.search(r"ROUND\s*([1-4])",banner,re.I)[1])
        seconds=self.turn_seconds(image)
        report["seconds_left"]=seconds
        report["our_turn"]="yourturn" in normalize(banner)
        report["resources"]={}
        for label,reference,ax,ay in self.RESOURCE_BOXES:
            box=self.hud_box(reference,ax,ay)
            try:
                report["resources"][label]=self.number(image,box)
            except RecognitionError as error:
                report["resources"][label+"_error"]=str(error)
        raised=[]
        for side,(name_y,stat_y,star_y) in enumerate(((.54,.80,.785),(.09,.35,.335))):
            for i,x in enumerate(self.CENTERS):
                title=self.raised_title(image,x) if side==1 else ""
                name=title or self.title(image,(x-.055,name_y-.02,x+.065,name_y+.08),.8)
                marker=self.played_marker(image,x,side)
                entry={"side":side,"slot":i,"name":name,"used":marker}
                if marker:
                    try:
                        entry["paid_pillz"]=self.played_pillz(image,x,side)
                    except RecognitionError as error:
                        entry["paid_pillz_error"]=str(error)
                elif title:
                    raised.append(i)
                operations=(
                    ("power",lambda:self.number(image,self.stat_box(x,stat_y))),
                    ("damage",lambda:self.number(image,self.stat_box(x,stat_y,True))),
                    ("stars",lambda:self.stars(image,x,star_y)))
                if entry["used"]:
                    entry["stats_status"]="played card; retain previously verified base stats"
                    operations=()
                for label,operation in operations+(("catalog",lambda:self.catalog.identify(entry["name"],report["day"],None if entry["used"] else tuple(entry.get(k) for k in ("power","damage","stars"))).name),):
                    try:
                        entry[label]=operation()
                    except ValueError as error:
                        entry[label+"_error"]=str(error)
                report["cards"].append(entry)
        report["observed_card"]=raised[0] if len(raised)==1 else None
        if len(raised)>1:
            report["lead_error"]="Multiple raised opponent titles"
        report["recognition_complete"]=all(
            c["name"] and not any(key.endswith("_error") and key!="catalog_error" for key in c)
            for c in report["cards"]) and not any(key.endswith("_error") for key in report["resources"]) and len(raised)<=1
        if any(sum(c["used"] for c in report["cards"] if c["side"]==side)!=report["round"]-1 for side in range(2)):
            report["played_count_error"]="Played-card markers disagree with the round number"
            report["recognition_complete"]=False
        report["recognition_complete"] = report["recognition_complete"] and report["seconds_left"] is not None
        report["engine_ready"]=report["recognition_complete"] and all("catalog_error" not in c for c in report["cards"])
        return report

    def board(self,image,previous=None,submitted=None,allow_mid_match=False):
        cached_banner=getattr(self,"_last_banner",None)
        if cached_banner is not None and cached_banner[0]==id(image):
            banner=cached_banner[1]
            self._last_banner=None
        else:
            banner=self.text(image,(.27,.46,.73,.55),.8)
        if "yourturn" not in normalize(banner):
            return None
        match=re.search(r"ROUND\s*(\d)\s*[/|]\s*4",banner,re.I)
        seconds=self.turn_seconds(image)
        if seconds is not None and seconds<12:
            raise RecognitionError("Fewer than 12 seconds remain; stopping before a rushed input")
        if not match or seconds is None:
            # A raised/flipping card can occlude the round banner. This frame
            # authorizes no action; wait for a complete board instead of ending
            # the session on a short animation. Known short clocks still stop.
            return None
        round_no=int(match[1])
        if previous is None and round_no!=1 and not allow_mid_match:
            raise RecognitionError("Start recognition at round 1 before any card is played")
        if allow_mid_match and previous is not None and round_no<previous.round:
            self.initial_hand=None
            previous=None
        day=self.day(image)
        hands=[]
        spent=[]
        raised_titles={}
        for side, (name_y,overlay_y,stat_y,star_y) in enumerate(((.54,.65,.80,.785),(.09,.20,.35,.335))):
            hand=[]
            used=[]
            for i,x in enumerate(self.CENTERS):
                if side==1:
                    rt=self.raised_title(image,x,.8)
                    raised_titles[i]=rt
                    text=rt or self.title(image,(x-.055,name_y-.02,x+.065,name_y+.08),.8)
                else:
                    text=self.card_name(image,x,name_y,side,.8)
                played=self.played_pillz(image,x,side)
                used.append(played)
                cached=None
                if self.initial_hand is not None:
                    prev_card=self.initial_hand[side][i]
                    if normalize(text)==normalize(prev_card.name):
                        cached=prev_card
                    elif self.catalog.star_catalog is not None and played is not None:
                        # Dimmed played cards have low-contrast titles; retain Round 1 identity.
                        cached=prev_card
                    elif self.catalog.star_catalog is not None and text.strip():
                        resolved=self.catalog.star_catalog.resolve(text)
                        if resolved is not None and resolved.norm_name==normalize(prev_card.name):
                            cached=prev_card
                if cached is not None:
                    c=cached
                elif self.initial_hand is not None and not text.strip():
                    # Card is mid-animation/flipping; wait for a clean board frame.
                    return None
                elif self.initial_hand is not None and not allow_mid_match:
                    raise RecognitionError("Hand/order changed; start a fresh session for each match")
                elif allow_mid_match and played is not None:
                    try:
                        c=self.catalog.identify(text,day,None)
                    except RecognitionError:
                        c=Card(name=text.strip() or f"Played-{side}-{i+1}",power=1,damage=1,stars=1,clan="Unknown")
                else:
                    stars=self.stars(image,x,star_y)
                    if self.catalog.star_catalog is not None:
                        evo=self.catalog.star_catalog.resolve(text,stars=stars)
                        if evo is not None:
                            c=evo.card
                        else:
                            power=self.number(image,self.stat_box(x,stat_y))
                            damage=self.number(image,self.stat_box(x,stat_y,True))
                            c=self.catalog.identify(text,day,(power,damage,stars))
                    else:
                        power=self.number(image,self.stat_box(x,stat_y))
                        damage=self.number(image,self.stat_box(x,stat_y,True))
                        c=self.catalog.identify(text,day,(power,damage,stars))
                hand.append(c)
            hands.append(tuple(hand))
            spent.append(tuple(used))
        hands=tuple(hands)

        if self.initial_hand is not None and not allow_mid_match and hands!=self.initial_hand:
            raise RecognitionError("Hand/order changed; start a fresh session for each match")
        resources=self.read_resources(image)
        life=(resources["our_life"],resources["opponent_life"])
        pillz=(resources["our_pillz"],resources["opponent_pillz"])
        if previous is None and round_no==1 and (not (1<=life[0]<=30 and 1<=life[1]<=30) or not (0<=pillz[0]<=20 and 0<=pillz[1]<=20)):
            raise RecognitionError("Opening resources out of valid match range")
        used=tuple(tuple(i for i,n in enumerate(row) if n is not None) for row in spent)
        if any(len(row)!=round_no-1 for row in used):
            raise RecognitionError("Played-card overlays disagree with round number")
        last=(None,None)
        leader=0
        observed=None
        lifted=[]
        # Lingering Poison/Heal/etc. are invisible on the board; carry them
        # from the engine's resolution of the previous round.
        lingering=((),())
        for i,x in enumerate(self.CENTERS):
            if i in used[1]:
                continue
            # A revealed opponent lead is enlarged upward. Require its name to
            # appear in the narrow raised title band, not just a bright card.
            title=raised_titles.get(i,"")
            if normalize(title)==normalize(hands[1][i].name):
                lifted.append(i)
        if len(lifted)>1:
            raise RecognitionError("Multiple opponent lead candidates")
        if lifted:
            leader,observed=1,lifted[0]
        if previous:
            if round_no==previous.round:
                last=tuple(p.last_won for p in previous.players)
                lingering=tuple(p.effects for p in previous.players)
                if leader!=previous.leader and not allow_mid_match:
                    raise RecognitionError("Initiative recognition changed within a round")
            elif round_no==previous.round+1 and submitted:
                leader=1-previous.leader
                if leader==1 and observed is None:
                    raise RecognitionError("Opponent lead has not been identified")
                new=[set(used[i])-set(previous.players[i].used) for i in range(2)]
                if any(len(s)!=1 for s in new) or submitted.card not in new[0]:
                    raise RecognitionError("Unexpected card transition")
                op_index=next(iter(new[1]))
                matches=[]
                carried=[]
                for fury in (False,True):
                    try:
                        after=resolve(previous,submitted,Move(op_index,spent[1][op_index],fury))
                    except ValueError:
                        continue
                    effects=tuple(p.effects for p in after.players)
                    carried.append(effects)
                    if tuple(p.life for p in after.players)==life and tuple(p.pillz for p in after.players)==pillz:
                        matches.append(tuple(p.last_won for p in after.players))
                        matched_effects=effects
                if len(matches)==1 or (matches and len(set(matches))==1):
                    lingering=matched_effects
                elif carried and len(set(carried))==1:
                    lingering=carried[0]
                else:
                    lingering=tuple(p.effects for p in previous.players)
                if not matches or len(set(matches))!=1:
                    if self.catalog.star_catalog is not None:
                        # Unmodeled bespoke abilities (e.g. Killshot, Poison, Consume)
                        # can shift live life/pillz vs the core engine; trust live HUD values.
                        our_lost=previous.players[0].life-life[0]
                        opp_lost=previous.players[1].life-life[1]
                        if opp_lost>0 and our_lost<=0:
                            last=(True,False)
                        elif our_lost>0 and opp_lost<=0:
                            last=(False,True)
                        else:
                            last=(None,None)
                    else:
                        raise RecognitionError("Live life/pillz do not reconcile with the engine; stopping")
                else:
                    last=matches[0]
            elif not allow_mid_match:
                raise RecognitionError("Missed a round; cannot reconstruct public state safely")
        elif round_no!=1 and not allow_mid_match:
            raise RecognitionError("Start recognition at round 1 before any card is played")
        players=tuple(Player(hands[i],life[i],pillz[i],used[i],last[i],lingering[i]) for i in range(2))
        state=State(players,leader,round_no,day)
        self.initial_hand=hands
        return Board(state,observed,seconds,tuple(spent))


class VisionSession:
    """Single-match, single-action-per-frame state machine. Defaults to inspect."""
    def __init__(self, reader=None, execute=False, iterations=500, clock=time.monotonic, mode="training", advisor=False, calibration=None):
        if mode not in VALID_MODES:
            raise ValueError(f"Unsupported mode: {mode!r}")
        self.reader=reader or CanvasReader()
        self.execute=execute
        self.advisor=advisor
        self.mode=mode
        self.iterations=iterations
        self.session_id=uuid.uuid4().hex
        self.state=None
        self.submitted=None
        self.pending=None
        self.phase="board"
        self.remaining=0
        self.base_attack=None
        self.expected_attack=None
        self.awaiting_round=None
        self.panel_power=None
        self.panel_damage=None
        self.clock=clock
        self.board_candidate=None
        self.board_candidate_at=None
        self.panel_candidate=None
        self.panel_candidate_at=None
        # Only user-saved calibration (see calibration.load_saved_calibration).
        self.calibration=calibration
        self.fury_on=False
        self.expected_damage=None
        self._min_attempts=0
        self._fury_attempts=0

    def hand_point(self,index):
        key=f"hand_{index}"
        if self.calibration and key in self.calibration:
            pt=self.calibration[key]
            return float(pt["x"]),float(pt["y"])
        return self.reader.CENTERS[index],.69

    def stake_targets(self,image):
        locate=getattr(self.reader,"stake_targets",None)
        if locate is None:
            return stake_layout([],self.calibration)
        return locate(image,self.calibration)

    def reset_stability(self):
        """Require fresh agreement after a focus pause; retain action receipts."""
        self.board_candidate=None
        self.board_candidate_at=None
        self.panel_candidate=None
        self.panel_candidate_at=None

    def action(self,x,y,status):
        self.panel_candidate=None
        res = {"status":status,"action":{"type":"click","x":x,"y":y} if self.execute else None}
        if getattr(self, "_last_recommendation", None) is not None:
            res["recommendation"] = self._last_recommendation
        return res

    def step(self,image):
        # Avoid a full-screen detector pass before a complete round-board read.
        # Menus, results, login screens and stake panels retain full-screen OCR.
        round_scene=(self.phase=="board" and hasattr(self.reader,"round_scene")
                     and self.reader.round_scene(image))
        stake_hint=False
        if self.phase!="board" and isinstance(self.reader,CanvasReader):
            btn_text=self.reader.text(image,(.60,.64,.85,.72),.7)
            stake_hint="confirmthestake" in normalize(btn_text)
            if not stake_hint:
                # The panel can sit off the reference box; search the whole panel area.
                stake_hint=self.reader.stake_open(image)
            if not stake_hint and self.phase=="selected" and not getattr(self,"_panel_seen",False) and self.reader.round_scene(image):
                waits=getattr(self,"_panel_wait",0)
                if waits==1:
                    self._panel_wait=waits+1
                    card_name=self.state.players[0].hand[self.pending.card].name
                    return self.action(*self.hand_point(self.pending.card),
                                       f"Round {self.state.round}: retry select {card_name}")
                if waits<3:
                    self._panel_wait=waits+1
                    return {"status":"Waiting for stake panel to open", "action":None}
        text=("YOUR TURN" if round_scene else
              "CONFIRM THE STAKE" if stake_hint else
              self.reader.text(image,(0,0,1,1),.8))
        norm=normalize(text)
        if "login" in norm or "playasguest" in norm:
            raise RecognitionError("Game requires sign-in; no login is automated")
        if "playagain" in norm and ("victory" in norm or "defeat" in norm):
            return {"status":"Match ended; no automatic requeue", "stop":True}
        stake="confirmthestake" in norm
        if self.phase=="board":
            if stake:
                if self.advisor and not self.execute:
                    res={"status":"Advisor: stake panel open; waiting for next round","action":None}
                    if getattr(self,"_last_recommendation",None) is not None:
                        res["recommendation"]=self._last_recommendation
                    return res
                raise RecognitionError("Unexpected open stake panel; close it before starting")
            if self.advisor and not self.execute:
                board=self.reader.board(image,self.state,self.submitted,allow_mid_match=True)
            else:
                board=self.reader.board(image,self.state,self.submitted)
            if board is None:
                self.board_candidate=None
                return {"status":"Waiting for a readable YOUR TURN board", "action":None}
            if self.awaiting_round==board.state.round:
                return {"status":"Waiting for round submission receipt", "action":None}
            if self.execute:
                # Compare public state, not the ticking timer or animated pixels.
                fingerprint=(board.state,board.observed_card,board.spent)
                now=self.clock()
                settled=(fingerprint==self.board_candidate
                         and self.board_candidate_at is not None
                         and 0 <= now-self.board_candidate_at <= 20)
                self.board_candidate=fingerprint
                self.board_candidate_at=now
                if not settled:
                    return {"status":"Waiting for a second matching board reading", "action":None}
                self.board_candidate=None
            self.state=board.state
            if not self.execute:
                if self.advisor:
                    rec = recommend_move(self.state, side=0, observed_card=board.observed_card, mode=self.mode)
                    self._last_recommendation = rec.to_dict()
                    return {"status":f"Advisor: {rec.reason}", "round":self.state.round,
                            "cards":[[c.name for c in p.hand] for p in self.state.players],
                            "recommendation":self._last_recommendation, "action":None}
                return {"status":"Inspect: board recognized", "round":self.state.round,
                        "cards":[[c.name for c in p.hand] for p in self.state.players],"action":None}
            rec = recommend_move(self.state, side=0, observed_card=board.observed_card, mode=self.mode)
            self.pending = Move(rec.card_index, rec.pillz, rec.fury)
            self._last_recommendation = rec.to_dict()
            selected=self.state.players[0].hand[self.pending.card]
            effects=selected.ability
            if sum(c.clan==selected.clan for c in self.state.players[0].hand)>=2:
                effects+=selected.bonus
            def _cond_active(cond):
                if cond=="always": return True
                if cond=="courage": return self.state.leader==0
                if cond=="reprisal": return self.state.leader==1
                if cond=="confidence": return self.state.players[0].last_won is True
                if cond=="revenge": return self.state.players[0].last_won is False
                if cond=="day": return self.state.day is True
                if cond=="night": return self.state.day is False
                return False
            own_power=[e for e in effects if e.stat=="power" and not e.opponent and e.multiplier=="none" and _cond_active(e.condition)]
            own_attack=[e for e in effects if e.stat=="attack" and not e.opponent and e.multiplier=="none" and _cond_active(e.condition)]
            own_damage=[e for e in effects if e.stat=="damage" and not e.opponent and e.multiplier=="none" and _cond_active(e.condition)]
            self.panel_power=max(1,selected.power+sum(e.amount for e in own_power))
            self.panel_attack_bonus=sum(e.amount for e in own_attack)
            self.panel_damage=max(1,selected.damage+sum(e.amount for e in own_damage))
            self.expected_damage=self.panel_damage
            self.fury_on=False
            self._min_attempts=0
            self._fury_attempts=0
            self.phase="selected"
            self._panel_wait=0
            self._panel_seen=False
            return self.action(*self.hand_point(self.pending.card),
                               f"Round {self.state.round}: select {self.state.players[0].hand[self.pending.card].name}")
        if not stake:
            if isinstance(self.reader,CanvasReader) and self.state is not None:
                if self.reader.round_scene(image):
                    cached=getattr(self.reader,"_last_banner",None)
                    btxt=cached[1] if cached else ""
                    m=re.search(r"ROUND\s*(\d)\s*[/|]\s*4",btxt,re.I)
                    if m and int(m[1])>self.state.round:
                        # Round already advanced (e.g. manual confirm or fast resolve);
                        # resume seamlessly on the new round instead of stopping.
                        self.submitted=self.pending
                        self.phase="board"
                        self.panel_candidate=None
                        self._panel_wait=0
                        self._panel_seen=False
                        return {"status":f"Round {int(m[1])} started; reading board", "action":None}
            if self.phase=="selected" and getattr(self,"_panel_wait",0)<5:
                self._panel_wait=getattr(self,"_panel_wait",0)+1
                return {"status":"Waiting for stake panel or next round", "action":None}
            # Animation after confirm is expected, otherwise no blind clicks.
            raise RecognitionError("Stake panel disappeared before a verified submission")
        self._panel_wait=0
        self._panel_seen=True
        selected=self.reader.text(image,(.32,.20,.47,.27),.8)
        expected=self.state.players[0].hand[self.pending.card].name
        name_ok=(normalize(selected)==normalize(expected))
        if not name_ok and getattr(getattr(self.reader,"catalog",None),"star_catalog",None) is not None and selected.strip():
            resolved=self.reader.catalog.star_catalog.resolve(selected)
            name_ok=(resolved is not None and resolved.norm_name==normalize(expected))
        if not name_ok:
            raise RecognitionError(f"Selected card differs from {expected}: {selected!r}")
        panel_number=getattr(self.reader,"panel_number",None)
        attack=(panel_number(image,CanvasReader.PANEL_ATTACK,"attack") if panel_number
                else self.reader.number(image,CanvasReader.PANEL_ATTACK))
        damage=(panel_number(image,CanvasReader.PANEL_DAMAGE,"damage") if panel_number
                else self.reader.number(image,CanvasReader.PANEL_DAMAGE))
        fingerprint=(self.phase,normalize(selected),attack,damage)
        now=self.clock()
        settled=(fingerprint==self.panel_candidate and self.panel_candidate_at is not None
                 and 0 <= now-self.panel_candidate_at <= 20)
        self.panel_candidate=fingerprint
        self.panel_candidate_at=now
        if not settled:
            return {"status":"Waiting for a second matching stake-panel reading", "action":None}
        targets=self.stake_targets(image)
        src=targets["_source"]
        def at(key,status):
            x,y=targets[key]
            return self.action(x,y,f"{status} [{key.upper()} via {src[key]}]")
        if self.phase=="fury" and damage==self.panel_damage and self._fury_attempts<2:
            # The Fury toggle did not register (damage unchanged): retry once.
            self._fury_attempts+=1
            return at("fury","Fury did not register; retry once")
        if damage!=self.expected_damage:
            raise RecognitionError(
                f"Damage panel shows {damage}, expected {self.expected_damage} "
                f"({'with' if self.fury_on else 'no'} Fury)")
        if self.phase=="selected":
            self.phase="reset"
            self._min_attempts=1
            return at("min","Reset paid pillz to zero")
        all_in=False
        if self.phase=="reset":
            atk_bonus=getattr(self,"panel_attack_bonus",0)
            self.base_attack=self.panel_power
            if attack!=self.panel_power+atk_bonus:
                if self._min_attempts<2:
                    self._min_attempts+=1
                    return at("min","MIN did not reach zero paid pillz; retry once")
                raise RecognitionError("MIN did not confirm zero paid pillz at the expected power")
            # A fresh panel defaults Fury off; never reuse a manually edited panel.
            self.remaining=self.pending.pillz
            self.expected_attack=attack
            if self.pending.fury:
                if "fury" in targets:
                    self.phase="fury"
                    self.fury_on=True
                    self.expected_damage=self.panel_damage+2
                    self._fury_attempts=1
                    return at("fury","Turn on Fury; verify +2 damage")
                # No Fury button found on screen or in calibration: keep the
                # same paid pillz and submit honestly without Fury.
                self.pending=Move(self.pending.card,self.pending.pillz,False)
            self.phase="increment"
            all_in=True
        elif self.phase=="fury":
            if attack!=self.expected_attack:
                raise RecognitionError("Fury changed the displayed attack unexpectedly")
            self.phase="increment"
        elif self.phase=="increment" and attack!=self.expected_attack:
            raise RecognitionError("Displayed attack does not confirm the last pillz increment")
        if (all_in and not self.fury_on and self.remaining
                and self.remaining==self.state.players[0].pillz):
            # MAX is only used for an exact all-in allocation, after verified
            # MIN/no-Fury. Its resulting attack must still settle and match.
            atk_bonus=getattr(self,"panel_attack_bonus",0)
            self.expected_attack=self.base_attack*(self.remaining+1)+atk_bonus
            self.remaining=0
            return at("max","Allocate all remaining paid pillz with MAX; verify attack")
        if self.remaining:
            self.remaining-=1
            self.expected_attack+=self.base_attack
            return at("plus","Add one paid pill; verify attack on the next frame")
        # Mark attempted BEFORE the external click. Never retry confirmation.
        self.submitted=self.pending
        self.awaiting_round=self.state.round
        self.phase="board"
        fury_text="with Fury" if self.pending.fury else "no Fury"
        return at("confirm",f"Confirm {self.pending.pillz} paid pillz, {fury_text}")
