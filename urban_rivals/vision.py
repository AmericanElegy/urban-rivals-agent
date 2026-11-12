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
        scale=1 if crop.width>650 else 3
        crop = ImageOps.expand(crop.resize((crop.width*scale,crop.height*scale)), border=12, fill="black")
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

    def detect(self,pixels,detail=False):
        """Restore shared detector settings even when inference fails."""
        detector=self.model.text_det
        previous=detector.limit_side_len
        try:
            detector.limit_side_len=736 if detail else 192
            return self.model(pixels)
        finally:
            detector.limit_side_len=previous

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
    def __init__(self, path=None):
        path = Path(path) if path else Path(__file__).parent / "data" / "training_cards.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("schema") != "urban-rivals/cards/v1":
            raise ValueError("Unknown catalog schema")
        self.entries = {}
        for raw in data["cards"]:
            raw = dict(raw)
            day_only = raw.pop("day_only",False)
            for field in ("ability","bonus"):
                raw[field] = parse_effect(raw.get(field,""))
            card = Card(**raw)
            key = normalize(card.name)
            if key in self.entries:
                raise ValueError("Duplicate catalog identity")
            self.entries[key] = (card,day_only)

    def identify(self,text,day):
        key=normalize(text)
        matches=[entry for name,entry in self.entries.items() if key == name]
        if len(matches) != 1:
            raise RecognitionError(f"Unknown or ambiguous card name: {text!r}; add its verified evolution to the catalog")
        card, day_only = matches[0]
        if day_only and day is not True:
            raise RecognitionError(f"{card.name}: only the observed Day bonus is cataloged")
        return card


@dataclass(frozen=True)
class Board:
    state: State
    observed_card: int | None
    seconds_left: int
    spent: tuple[tuple[int | None, ...], ...]


class CanvasReader:
    CENTERS=(.221,.406,.591,.776)

    def __init__(self,ocr=None,catalog=None):
        self.ocr=ocr or LocalOCR()
        self.catalog=catalog or Catalog()
        self.initial_hand=None

    def text(self,image,box,minimum=.85):
        return self.ocr.text(image,box,minimum)

    def round_scene(self,image):
        """A phase hint only: board() must still verify the complete state."""
        banner=self.text(image,(.27,.46,.73,.55),.8)
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
        """Find the white selection disc, not letters in scenery above a card."""
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
        strip=pixels[int((y-.012)*h):int((y+.012)*h),int((x-.05)*w):int((x+.05)*w)]
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
        p=np.array(image.crop((int(w*.79),0,int(w*.825),int(h*.08))).convert("RGB"))
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
        seconds=parse_timer(self.precise_text(image,(.64,.46,.73,.54),.8))
        report["seconds_left"]=seconds
        report["our_turn"]="yourturn" in normalize(banner)
        report["resources"]={}
        for label,box in (("our_life",(.76,.90,.81,.99)),("opponent_life",(.22,0,.275,.08)),
                          ("our_pillz",(.68,.90,.735,.99)),("opponent_pillz",(.30,0,.35,.08))):
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
                for label,operation in operations+(("catalog",lambda:self.catalog.identify(entry["name"],report["day"]).name),):
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

    def board(self,image,previous=None,submitted=None):
        banner=self.text(image,(.27,.46,.73,.55),.8)
        if "yourturn" not in normalize(banner):
            return None
        match=re.search(r"ROUND\s*(\d)\s*[/|]\s*4",banner,re.I)
        seconds=parse_timer(self.precise_text(image,(.64,.46,.73,.54),.8))
        if not match or seconds is None:
            raise RecognitionError(f"Round/timer is unreadable: {banner!r}")
        round_no=int(match[1])
        if seconds<12:
            raise RecognitionError("Fewer than 12 seconds remain; stopping before a rushed input")
        day=self.day(image)
        hands=[]
        spent=[]
        for side, (name_y,overlay_y,stat_y,star_y) in enumerate(((.54,.65,.80,.785),(.09,.20,.35,.335))):
            hand=[]
            used=[]
            for i,x in enumerate(self.CENTERS):
                text=self.card_name(image,x,name_y,side,.8)
                c=self.catalog.identify(text,day)
                used.append(self.played_pillz(image,x,side))
                if self.initial_hand is None:
                    power=self.number(image,self.stat_box(x,stat_y))
                    damage=self.number(image,self.stat_box(x,stat_y,True))
                    stars=self.stars(image,x,star_y)
                    if (power,damage,stars)!=(c.power,c.damage,c.stars):
                        raise RecognitionError(f"{c.name}: screen stats/level disagree with catalog")
                hand.append(c)
            hands.append(tuple(hand))
            spent.append(tuple(used))
        hands=tuple(hands)
        if any(c.clan!="Bangers" for c in hands[0]):
            raise RecognitionError("First live input profile supports the cataloged Bangers hand only")
        if self.initial_hand is not None and hands!=self.initial_hand:
            raise RecognitionError("Hand/order changed; start a fresh session for each match")
        life=(self.number(image,(.76,.90,.81,.99)),self.number(image,(.22,0,.275,.08)))
        pillz=(self.number(image,(.68,.90,.735,.99)),self.number(image,(.30,0,.35,.08)))
        used=tuple(tuple(i for i,n in enumerate(row) if n is not None) for row in spent)
        if any(len(row)!=round_no-1 for row in used):
            raise RecognitionError("Played-card overlays disagree with round number")
        last=(None,None)
        leader=0
        observed=None
        lifted=[]
        for i,x in enumerate(self.CENTERS):
            if i in used[1]:
                continue
            # A revealed opponent lead is enlarged upward. Require its name to
            # appear in the narrow raised title band, not just a bright card.
            title=self.raised_title(image,x,.8)
            if normalize(title)==normalize(hands[1][i].name):
                lifted.append(i)
        if len(lifted)>1:
            raise RecognitionError("Multiple opponent lead candidates")
        if lifted:
            leader,observed=1,lifted[0]
        if previous:
            if round_no==previous.round:
                last=tuple(p.last_won for p in previous.players)
                if leader!=previous.leader:
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
                for fury in (False,True):
                    try:
                        after=resolve(previous,submitted,Move(op_index,spent[1][op_index],fury))
                    except ValueError:
                        continue
                    if tuple(p.life for p in after.players)==life and tuple(p.pillz for p in after.players)==pillz:
                        matches.append(tuple(p.last_won for p in after.players))
                if not matches or len(set(matches))!=1:
                    raise RecognitionError("Live life/pillz do not reconcile with the engine; stopping")
                last=matches[0]
            else:
                raise RecognitionError("Missed a round; cannot reconstruct public state safely")
        elif round_no!=1:
            raise RecognitionError("Start recognition at round 1 before any card is played")
        players=tuple(Player(hands[i],life[i],pillz[i],used[i],last[i]) for i in range(2))
        state=State(players,leader,round_no,day)
        self.initial_hand=hands
        return Board(state,observed,seconds,tuple(spent))


class VisionSession:
    """Single-match, single-action-per-frame state machine. Defaults to inspect."""
    def __init__(self, reader=None, execute=False, iterations=500, clock=time.monotonic):
        self.reader=reader or CanvasReader()
        self.execute=execute
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

    def action(self,x,y,status):
        self.panel_candidate=None
        return {"status":status,"action":{"type":"click","x":x,"y":y} if self.execute else None}

    def step(self,image):
        # Avoid a full-screen detector pass before a complete round-board read.
        # Menus, results, login screens and stake panels retain full-screen OCR.
        round_scene=(self.phase=="board" and hasattr(self.reader,"round_scene")
                     and self.reader.round_scene(image))
        text="YOUR TURN" if round_scene else self.reader.text(image,(0,0,1,1),.8)
        norm=normalize(text)
        if "login" in norm or "playasguest" in norm:
            raise RecognitionError("Game requires sign-in; no login is automated")
        if "playagain" in norm and ("victory" in norm or "defeat" in norm):
            return {"status":"Match ended; no automatic requeue", "stop":True}
        stake="confirmthestake" in norm
        if self.phase=="board":
            if stake:
                raise RecognitionError("Unexpected open stake panel; close it before starting")
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
                return {"status":"Inspect: board recognized", "round":self.state.round,
                        "cards":[[c.name for c in p.hand] for p in self.state.players],"action":None}
            advice=advise(self.state,0,board.observed_card,self.iterations,allow_fury=False)
            import random
            self.pending=random.SystemRandom().choices(advice.moves,advice.probabilities,k=1)[0]
            selected=self.state.players[0].hand[self.pending.card]
            effects=selected.ability
            if sum(c.clan==selected.clan for c in self.state.players[0].hand)>=2:
                effects+=selected.bonus
            own_power=[e for e in effects if e.stat=="power" and not e.opponent]
            if any(e.condition!="always" or e.multiplier!="none" for e in own_power):
                raise RecognitionError("Selected card needs an uncalibrated attack-panel rule")
            self.panel_power=selected.power+sum(e.amount for e in own_power)
            self.panel_damage=selected.damage
            self.phase="selected"
            return self.action(self.reader.CENTERS[self.pending.card],.69,
                               f"Round {self.state.round}: select {self.state.players[0].hand[self.pending.card].name}")
        if not stake:
            # Animation after confirm is expected, otherwise no blind clicks.
            raise RecognitionError("Stake panel disappeared before a verified submission")
        selected=self.reader.text(image,(.32,.20,.47,.27),.8)
        expected=self.state.players[0].hand[self.pending.card].name
        if normalize(selected)!=normalize(expected):
            raise RecognitionError(f"Selected card differs from {expected}: {selected!r}")
        panel_number=getattr(self.reader,"panel_number",None)
        attack=(panel_number(image,(.55,.55,.61,.64),"attack") if panel_number
                else self.reader.number(image,(.55,.55,.61,.64)))
        damage=(panel_number(image,(.74,.55,.79,.64),"damage") if panel_number
                else self.reader.number(image,(.74,.55,.79,.64)))
        fingerprint=(self.phase,normalize(selected),attack,damage)
        now=self.clock()
        settled=(fingerprint==self.panel_candidate and self.panel_candidate_at is not None
                 and 0 <= now-self.panel_candidate_at <= 20)
        self.panel_candidate=fingerprint
        self.panel_candidate_at=now
        if not settled:
            return {"status":"Waiting for a second matching stake-panel reading", "action":None}
        if damage!=self.panel_damage:
            raise RecognitionError("Damage panel differs from the no-Fury expectation")
        if self.phase=="selected":
            self.phase="reset"
            return self.action(.578,.513,"Reset paid pillz to zero")
        if self.phase=="reset":
            self.base_attack=attack
            if attack!=self.panel_power:
                raise RecognitionError("MIN did not confirm zero paid pillz at the expected power")
            # Fury is intentionally not enabled by the first live driver. A
            # fresh panel defaults off; never reuse a manually edited panel.
            self.remaining=self.pending.pillz
            self.expected_attack=attack
            self.phase="increment"
            if self.remaining and self.remaining==self.state.players[0].pillz:
                # MAX is only used for an exact all-in allocation, after verified
                # MIN/no-Fury. Its resulting attack must still settle and match.
                self.expected_attack=self.base_attack*(self.remaining+1)
                self.remaining=0
                return self.action(.874,.513,"Allocate all remaining paid pillz with MAX; verify attack")
        elif self.phase=="increment" and attack!=self.expected_attack:
            raise RecognitionError("Displayed attack does not confirm the last pillz increment")
        if self.remaining:
            self.remaining-=1
            self.expected_attack+=self.base_attack
            return self.action(.874,.442,"Add one paid pill; verify attack on the next frame")
        # Mark attempted BEFORE the external click. Never retry confirmation.
        self.submitted=self.pending
        self.awaiting_round=self.state.round
        self.phase="board"
        return self.action(.722,.675,f"Confirm {self.pending.pillz} paid pillz, no Fury")
