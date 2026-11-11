"""Regression against two public training-round receipts observed 2026-11-11.

These rounds were observed during calibration, not attributed to this program.
Used-card overlays show total attack pillz (paid + free), not Fury cost.
"""
import unittest
from urban_rivals.engine import Player, State, Move, resolve
from urban_rivals.vision import Catalog


class ObservedRoundTests(unittest.TestCase):
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
