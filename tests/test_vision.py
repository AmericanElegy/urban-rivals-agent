import unittest
from urban_rivals.bridge import validate_frame
from urban_rivals.vision import Catalog, RecognitionError, VisionSession, Board
from urban_rivals.engine import Card, Player, State, Move


class ProtocolTests(unittest.TestCase):
    def test_menu_is_classified_without_inventing_card_reads(self):
        from urban_rivals.vision import CanvasReader
        class OCRStub:
            def text(self,image,box,minimum):
                return "TRAINING UNNAMED DECK compatible PLAY More info" if box==(0,0,1,1) else "PLAY"
        reader=object.__new__(CanvasReader)
        reader.ocr=OCRStub()
        result=reader.diagnostics(None)
        self.assertEqual(result["phase"],"training_menu")
        self.assertEqual(result["cards"],[])

    def test_raised_title_ignores_background_digits_and_single_letters(self):
        from urban_rivals.vision import CanvasReader
        class OCRStub:
            def text(self,image,box,minimum):
                return self.raised if box[1]==.075 else "BARCIUS"
        reader=object.__new__(CanvasReader)
        reader.ocr=OCRStub()
        reader.raised_marker=lambda image,x: True
        for contamination in ("E","1 2",""):
            reader.ocr.raised=contamination
            self.assertEqual(reader.card_name(None,.4,.09,1),"BARCIUS")
        reader.ocr.raised="AUSTIN"
        self.assertEqual(reader.card_name(None,.2,.09,1),"AUSTIN")
    def test_viewport_crop_scales_and_rejects_bad_geometry(self):
        from urban_rivals.bridge import crop_viewport
        class ImageStub:
            width=3840
            height=2160
            def crop(self,box):
                return box
        geometry=dict(x=100,y=50,width=1000,height=600,viewportWidth=1920,viewportHeight=1080)
        self.assertEqual(crop_viewport(ImageStub(),geometry),(200,100,2200,1300))
        for bad in (dict(geometry,x=-1),dict(geometry,width=3000),dict(geometry,x=float("nan"))):
            with self.assertRaises(ValueError):
                crop_viewport(ImageStub(),bad)

    def frame(self):
        return dict(schema="urban-rivals/frame/v1",url="https://www.urban-rivals.com/game/play/webgl/",
                    captured_at=100,sequence=1,run_id="a"*32,mode="training",execute=False)

    def test_reject_stale_and_wrong_origin(self):
        f=self.frame()
        validate_frame(f,now=105)
        for bad in (dict(f,captured_at=80),dict(f,captured_at=106),dict(f,url="https://evil.test/"),dict(f,mode="tourney"),dict(f,sequence=True),dict(f,execute="yes")):
            with self.assertRaises(ValueError):
                validate_frame(bad,now=105)

    def test_catalog_is_exact_and_day_restricted(self):
        c=Catalog()
        self.assertEqual(c.identify("GRAFF CR",True).stars,1)
        self.assertEqual(c.identify("Vermyn Noël",True).name,"Vermyn Noel")
        for name,day in (("Graff",True),("Cooak",None),("Unknown",True)):
            with self.assertRaises(RecognitionError):
                c.identify(name,day)


class FakeReader:
    CENTERS=(.22,.40,.59,.77)
    def __init__(self):
        card=Card("Test",7,4,3,"Test")
        self.state=State((Player((card,),pillz=0),Player((card,),pillz=0)))
        self.panel=False
        self.attack=7

    def text(self,image,box,minimum=.85):
        if box==(0,0,1,1):
            return "CONFIRM THE STAKE" if self.panel else "YOUR TURN"
        return "Test"

    def number(self,image,box):
        return 4 if box==(.74,.55,.79,.64) else self.attack

    def board(self,*args):
        return Board(self.state,None,90,((None,),(None,)))


class SessionTests(unittest.TestCase):
    def panel_step(self,session):
        self.assertIsNone(session.step(None)["action"])
        return session.step(None)

    def test_round_hint_skips_full_screen_ocr_but_still_requires_board_read(self):
        class RoundReader(FakeReader):
            read=False
            def round_scene(self,image):
                return True
            def text(self,*args):
                raise AssertionError("Redundant full-screen OCR")
            def board(self,*args):
                self.read=True
                return super().board(*args)
        reader=RoundReader()
        self.assertIsNone(VisionSession(reader).step(None)["action"])
        self.assertTrue(reader.read)

    def test_inspect_never_clicks(self):
        s=VisionSession(FakeReader())
        self.assertIsNone(s.step(None)["action"])

    def test_select_reset_confirm_then_wait(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        self.assertIsNone(s.step(None)["action"])
        self.assertEqual(s.step(None)["action"]["x"],.22)
        r.panel=True
        self.assertEqual(self.panel_step(s)["action"]["x"],.578)
        self.assertEqual(self.panel_step(s)["action"]["x"],.722)
        r.panel=False
        self.assertIsNone(s.step(None)["action"])

    def test_wrong_card_or_attack_stops(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        r.panel=True
        self.panel_step(s)
        s.phase="increment"
        s.expected_attack=14
        with self.assertRaises(RecognitionError):
            self.panel_step(s)

    def test_failed_minimum_reset_is_not_confirmed(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        r.panel=True
        self.panel_step(s)
        r.attack=14
        with self.assertRaises(RecognitionError):
            self.panel_step(s)

    def test_fury_damage_is_not_confirmed(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        r.panel=True
        self.panel_step(s)
        r.number=lambda image,box: 6 if box==(.74,.55,.79,.64) else 7
        with self.assertRaises(RecognitionError):
            self.panel_step(s)

    def test_board_change_or_long_gap_requires_another_read(self):
        from dataclasses import replace
        r=FakeReader()
        tick=[0]
        s=VisionSession(r,execute=True,iterations=10,clock=lambda:tick[0])
        self.assertIsNone(s.step(None)["action"])
        r.state=replace(r.state,players=(replace(r.state.players[0],life=11),r.state.players[1]))
        self.assertIsNone(s.step(None)["action"])
        tick[0]=21
        self.assertIsNone(s.step(None)["action"])
        tick[0]=22
        self.assertIsNotNone(s.step(None)["action"])

    def test_timer_changes_do_not_prevent_settling(self):
        from dataclasses import replace
        r=FakeReader()
        original=r.board
        seconds=iter((90,89))
        r.board=lambda *args:replace(original(),seconds_left=next(seconds))
        s=VisionSession(r,execute=True,iterations=10)
        self.assertIsNone(s.step(None)["action"])
        self.assertIsNotNone(s.step(None)["action"])

    def test_unreadable_board_breaks_consecutive_reads(self):
        r=FakeReader()
        original=r.board
        s=VisionSession(r,execute=True,iterations=10)
        self.assertIsNone(s.step(None)["action"])
        r.board=lambda *args:None
        self.assertIsNone(s.step(None)["action"])
        r.board=original
        self.assertIsNone(s.step(None)["action"])
        self.assertIsNotNone(s.step(None)["action"])

    def test_stale_attack_after_increment_never_repeats_click(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        s.pending=Move(0,1)
        r.panel=True
        self.assertEqual(self.panel_step(s)["action"]["x"],.578)
        self.assertEqual(self.panel_step(s)["action"]["x"],.874)
        with self.assertRaisesRegex(RecognitionError,"last pillz increment"):
            self.panel_step(s)

    def test_changing_panel_numbers_do_not_trigger_minimum(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        r.panel=True
        self.assertIsNone(s.step(None)["action"])
        r.attack=14
        self.assertIsNone(s.step(None)["action"])
        r.attack=7
        self.assertEqual(self.panel_step(s)["action"]["x"],.578)

    def test_all_in_uses_max_once_then_verifies_full_attack(self):
        from dataclasses import replace
        r=FakeReader()
        r.state=replace(r.state,players=tuple(replace(p,pillz=2) for p in r.state.players))
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        s.pending=Move(0,2)
        r.panel=True
        self.panel_step(s)
        action=self.panel_step(s)["action"]
        self.assertEqual((action["x"],action["y"]),(.874,.513))
        self.assertEqual(s.expected_attack,21)
        r.attack=21
        self.assertEqual(self.panel_step(s)["action"]["x"],.722)

    def test_focus_resume_requires_two_fresh_boards(self):
        s=VisionSession(FakeReader(),execute=True,iterations=10)
        self.assertIsNone(s.step(None)["action"])
        s.reset_stability()
        self.assertIsNone(s.step(None)["action"])
        self.assertIsNotNone(s.step(None)["action"])

    def test_focus_resume_preserves_pending_action_receipt(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        s.step(None)
        r.panel=True
        self.panel_step(s)
        self.assertIsNone(s.step(None)["action"])
        pending=s.pending
        s.reset_stability()
        self.assertEqual(s.phase,"reset")
        self.assertEqual(s.pending,pending)
        self.assertEqual(self.panel_step(s)["action"]["x"],.722)
