"""Regression against two public training-round receipts observed 2026-11-11.

These rounds were observed during calibration, not attributed to this program.
Used-card overlays show total attack pillz (paid + free), not Fury cost.
"""
import unittest
from urban_rivals.engine import Player, State, Move, resolve
from urban_rivals.vision import Catalog


class ObservedRoundTests(unittest.TestCase):
    def test_recorded_cosmohnuts_rounds_through_final_start(self):
        catalog=Catalog()
        own=tuple(catalog.identify(n,True) for n in ("Bennie","Fixit","Pacarezza","Vermyn Noel"))
        opponent=tuple(catalog.identify(n,True) for n in ("Austin","Barcius","Buford","Lucien"))
        current=State((Player(own,life=15),Player(opponent,life=15)),leader=1,day=True)
        current=resolve(current,Move(1,0),Move(0,5))
        self.assertEqual([(p.life,p.pillz) for p in current.players],[(7,12),(15,7)])
        # Vermyn's lower power still wins: zero-paid-pill tie, 2* versus 3*.
        current=resolve(current,Move(3,0),Move(1,0))
        self.assertEqual([(p.life,p.pillz) for p in current.players],[(7,12),(11,7)])
        current=resolve(current,Move(0,0),Move(2,3))
        # The 55s animation first shows life 4; its Bet effect then reaches 3.
        # The stable 57s ROUND 4 board is the completed receipt.
        self.assertEqual([(p.life,p.pillz) for p in current.players],[(3,12),(11,4)])
        self.assertEqual(current.round,4)
        self.assertEqual(current.leader,0)

    def test_bangers_vs_ghostown_riots_public_receipts(self):
        catalog=Catalog()
        own=tuple(catalog.identify(name,True) for name in ("Bennie","Graff Cr","Randal","Vermyn Noel"))
        opponent=tuple(catalog.identify(name,True) for name in ("Cooak","Taurite","Dr Web Ld","Fastbender"))
        start=State((Player(own,life=15),Player(opponent,life=15)),leader=1,day=True)
        # Randal's x7 vs Taurite's x1. Next visible board: ours 15/6,
        # opponent 11/12 (life / remaining paid pillz).
        second=resolve(start,Move(2,6),Move(1,0))
        self.assertEqual([(p.life,p.pillz) for p in second.players],[(15,6),(11,12)])
        # Bennie's x3 vs Dr Web Ld's x1. Opponent's -2 power/damage ability
        # reduces Bennie's damage to 1, while Riots restores one pill even on defeat.
        third=resolve(second,Move(0,2),Move(2,0))
        self.assertEqual([(p.life,p.pillz) for p in third.players],[(15,4),(10,13)])
        self.assertTrue(third.players[0].last_won)
        self.assertFalse(third.players[1].last_won)
