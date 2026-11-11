"""Local OCR of a cropped Unity canvas. No game API or cloud model is used."""
from dataclasses import dataclass
from pathlib import Path
import json
import re
import uuid
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
        self.model = RapidOCR(det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False)

    def text(self, image, box, minimum=.85):
        import numpy as np
        from PIL import ImageOps
        w,h = image.size
        x1,y1,x2,y2 = box
        crop = image.crop((int(x1*w),int(y1*h),int(x2*w),int(y2*h)))
        scale=1 if crop.width>650 else 3
        crop = ImageOps.expand(crop.resize((crop.width*scale,crop.height*scale)), border=12, fill="black")
        result, _ = self.model(np.array(crop)[:,:,::-1].copy())
        if not result:
            return ""
        return " ".join(item[1] for item in result if float(item[2]) >= minimum)

    def number(self,image,box):
        import numpy as np
        from PIL import Image
        w,h=image.size
        x1,y1,x2,y2=box
        crop=image.crop((int(x1*w),int(y1*h),int(x2*w),int(y2*h))).convert("RGB")
        # Stats use white digits over colored icons. Remove those colored icons
        # before OCR rather than accepting a low-confidence guess at a digit.
        pixels=np.array(crop)
        white=(pixels.min(axis=2)>175).astype("uint8")*255
        monochrome=Image.fromarray(white).convert("RGB")
        detected=self.text(monochrome,(0,0,1,1),.85)
        if detected.strip():
            return detected
        # Text detection can miss a thin standalone '1'. The numeric crop is
        # already located; direct recognition is allowed only at high confidence.
        result,_=self.model(np.array(monochrome),use_det=False,use_cls=False,use_rec=True)
        if result and float(result[0][1])>=.95 and re.fullmatch(r"\d{1,3}",result[0][0]):
            return result[0][0]
        return ""


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

    def card_name(self,image,x,y,side,minimum=.8):
        if side==1:
            raised=self.text(image,(x-.055,.055,x+.075,.105),minimum)
            if len(re.sub(r"[^a-z]","",normalize(raised)))>=3:
                return raised
        return self.text(image,(x-.055,y,x+.065,y+.08),minimum)

    def number(self,image,box):
        text=self.ocr.number(image,box) if hasattr(self.ocr,"number") else self.text(image,box)
        if not re.fullmatch(r"\s*\d{1,3}\s*",text):
            raise RecognitionError(f"Resource or attack count is unreadable: {text!r}")
        return int(text)

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
        for side,(name_y,stat_y,star_y) in enumerate(((.54,.80,.785),(.09,.35,.335))):
            for i,x in enumerate(self.CENTERS):
                entry={"side":side,"slot":i,"name":self.card_name(image,x,name_y,side,.7)}
                for label,operation in (
                    ("power",lambda:self.number(image,(x-.07,stat_y-.025,x-.045,stat_y+.025))),
                    ("damage",lambda:self.number(image,(x-.07,stat_y+.035,x-.045,stat_y+.09))),
                    ("stars",lambda:self.stars(image,x,star_y)),
                    ("catalog",lambda:self.catalog.identify(entry["name"],report["day"]).name)):
                    try:
                        entry[label]=operation()
                    except ValueError as error:
                        entry[label+"_error"]=str(error)
                report["cards"].append(entry)
        return report

    def board(self,image,previous=None,submitted=None):
        banner=self.text(image,(.27,.46,.73,.55),.8)
        if "yourturn" not in normalize(banner):
            return None
        match=re.search(r"ROUND\s*(\d)\s*[/|]\s*4",banner,re.I)
        timer=re.search(r"(\d{1,2}):(\d{2})",banner)
        if not match or not timer:
            raise RecognitionError(f"Round/timer is unreadable: {banner!r}")
        round_no=int(match[1])
        seconds=int(timer[1])*60+int(timer[2])
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
                overlay=self.text(image,(x-.055,overlay_y,x+.055,overlay_y+.12),.75)
                count=re.search(r"[xX×]\s*(\d{1,3})",overlay)
                used.append(int(count[1])-1 if count else None)
                if self.initial_hand is None:
                    power=self.number(image,(x-.07,stat_y-.025,x-.045,stat_y+.025))
                    damage=self.number(image,(x-.07,stat_y+.035,x-.045,stat_y+.09))
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
            title=self.text(image,(x-.05,.065,x+.07,.105),.8)
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
    def __init__(self, reader=None, execute=False, iterations=500):
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

    def action(self,x,y,status):
        return {"status":status,"action":{"type":"click","x":x,"y":y} if self.execute else None}

    def step(self,image):
        text=self.reader.text(image,(0,0,1,1),.8)
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
                return {"status":"Waiting for a readable YOUR TURN board", "action":None}
            if self.awaiting_round==board.state.round:
                return {"status":"Waiting for round submission receipt", "action":None}
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
        selected=self.reader.text(image,(.24,.18,.49,.29),.8)
        expected=self.state.players[0].hand[self.pending.card].name
        if normalize(selected)!=normalize(expected):
            raise RecognitionError(f"Selected card differs from {expected}: {selected!r}")
        if self.phase=="selected":
            self.phase="reset"
            return self.action(.578,.513,"Reset paid pillz to zero")
        attack=self.reader.number(image,(.55,.55,.61,.64))
        damage=self.reader.number(image,(.74,.55,.79,.64))
        if damage!=self.panel_damage:
            raise RecognitionError("Damage panel differs from the no-Fury expectation")
        if self.phase=="reset":
            self.base_attack=attack
            if attack!=self.panel_power:
                raise RecognitionError("MIN did not confirm zero paid pillz at the expected power")
            # Fury is intentionally not enabled by the first live driver. A
            # fresh panel defaults off; never reuse a manually edited panel.
            self.remaining=self.pending.pillz
            self.expected_attack=attack
            self.phase="increment"
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
