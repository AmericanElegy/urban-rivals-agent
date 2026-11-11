import unittest
from urban_rivals.bridge import validate_frame
from urban_rivals.vision import Catalog, RecognitionError, VisionSession, Board
from urban_rivals.engine import Card, Player, State, Move


class ProtocolTests(unittest.TestCase):
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
    def test_inspect_never_clicks(self):
        s=VisionSession(FakeReader())
        self.assertIsNone(s.step(None)["action"])

    def test_select_reset_confirm_then_wait(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        self.assertEqual(s.step(None)["action"]["x"],.22)
        r.panel=True
        self.assertEqual(s.step(None)["action"]["x"],.578)
        self.assertEqual(s.step(None)["action"]["x"],.722)
        r.panel=False
        self.assertIsNone(s.step(None)["action"])

    def test_wrong_card_or_attack_stops(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        r.panel=True
        s.step(None)
        s.phase="increment"
        s.expected_attack=14
        with self.assertRaises(RecognitionError):
            s.step(None)

    def test_failed_minimum_reset_is_not_confirmed(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        r.panel=True
        s.step(None)
        r.attack=14
        with self.assertRaises(RecognitionError):
            s.step(None)

    def test_fury_damage_is_not_confirmed(self):
        r=FakeReader()
        s=VisionSession(r,execute=True,iterations=10)
        s.step(None)
        r.panel=True
        s.step(None)
        r.number=lambda image,box: 6 if box==(.74,.55,.79,.64) else 7
        with self.assertRaises(RecognitionError):
            s.step(None)
