import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve, legal_moves
from urban_rivals.vision import Catalog


def c(name,power=7,damage=4,stars=3,ability="",bonus="",clan=None):
    return Card(name,power,damage,stars,clan or name,parse_effect(ability),parse_effect(bonus))


def state(a,b,leader=0):
    return State((Player((a,a),life=30),Player((b,b),life=30)),leader=leader)


class AbilityCopyTests(unittest.TestCase):
    def test_bonus_copies_ability_but_not_bonus(self):
        a=c("a",bonus="Copy: Opp. Ability")
        b=c("b",ability="Power +2",bonus="Power +3")
        after=resolve(state(a,b),Move(0,0),Move(0,0))
        self.assertTrue(after.players[1].last_won)  # 9 versus 12

    def test_copied_bonus_survives_stop_ability_and_stops_original(self):
        a=c("a",power=7,ability="Power +4",bonus="Copy: Opp. Ability")
        b=c("b",power=8,ability="Stop Opp. Ability")
        after=resolve(state(a,b),Move(0,0),Move(0,0))
        self.assertTrue(after.players[1].last_won)  # own +4 was stopped

    def test_copy_bonus_is_itself_disabled_by_stop_bonus(self):
        a=c("a",power=7,bonus="Copy: Opp. Ability")
        b=c("b",power=8,ability="Stop Opp. Bonus")
        after=resolve(state(a,b),Move(0,0),Move(0,0))
        self.assertTrue(after.players[1].last_won)

    def test_conditional_copy_uses_copier_initiative(self):
        a=c("a",power=7,bonus="Copy: Opp. Ability")
        b=c("b",power=8,ability="Reprisal: Power +3")
        self.assertFalse(resolve(state(a,b),Move(0,0),Move(0,0)).players[0].last_won)
        self.assertTrue(resolve(state(a,b,leader=1),Move(0,0),Move(0,0)).players[0].last_won)

    def test_copied_pillz_reward_applies_to_copier(self):
        a=c("a",power=10,bonus="Copy: Opp. Ability")
        b=c("b",ability="+3 Pillz")
        after=resolve(state(a,b),Move(0,0),Move(0,0))
        self.assertEqual(tuple(p.pillz for p in after.players),(15,12))

    def test_no_matching_clan_means_no_copy_bonus(self):
        a=c("a",power=7,bonus="Copy: Opp. Ability")
        b=c("b",power=8,ability="Reprisal: Power +3")
        s=State((Player((a,c("different"))),Player((b,b))),leader=1)
        self.assertFalse(resolve(s,Move(0,0),Move(0,0)).players[0].last_won)

    def test_leader_and_genesis_are_not_copied(self):
        for clan in ("Leader","Genesis"):
            a=c("a",power=7,bonus="Copy: Opp. Ability")
            b=c("b",power=8,ability="Power +3",clan=clan)
            self.assertFalse(resolve(state(a,b),Move(0,0),Move(0,0)).players[0].last_won)

    def test_observed_hand_all_round_one_pairings_resolve(self):
        catalog=Catalog()
        own=tuple(catalog.identify(n,True) for n in ("Fixit","Graff Cr","Joy","Pacarezza"))
        enemy=tuple(catalog.identify(n,True) for n in ("Gibus","Viperine","Wilmot","Gregor Ld"))
        for leader in (0,1):
            s=State((Player(own,life=15),Player(enemy,life=15)),leader=leader,day=True)
            # Every card and affordable paid/Fury allocation; exercise solver domain.
            for first in legal_moves(s,0):
                for second in legal_moves(s,1):
                    after=resolve(s,first,second)
                    self.assertEqual(after.round,2)
                    self.assertTrue(all(p.life>=0 and p.pillz>=0 for p in after.players))

    def test_live_log_matches_without_inventing_opponent_fury(self):
        from urban_rivals.replay import verify_battle_log
        result=verify_battle_log("tests/fixtures/live_copy_battle_log.json")
        self.assertTrue(result["passed"])
        self.assertEqual(result["matching_paths"],7)
        for history in result["possible_fury_histories"]:
            self.assertEqual([row[0] for row in history],[False,False,True,False])
        self.assertGreater(len(result["possible_final_pillz"]),1)

    def test_second_live_hand_preserves_budget_across_complete_matches(self):
        import random
        from urban_rivals.io import load_state
        rng=random.Random(31)
        for _ in range(20):
            state=load_state("examples/live_pussycats_training.json")
            while not state.terminal:
                state=resolve(state,rng.choice(legal_moves(state,0)),rng.choice(legal_moves(state,1)))
                self.assertTrue(all(p.life>=0 and p.pillz>=0 for p in state.players))

    def test_new_catalog_entries_resolve_against_the_training_deck(self):
        catalog=Catalog()
        our_names=("Bennie","Doug Snop","Fixit","Graff Cr","Joy","Pacarezza","Randal","Vermyn Noel")
        enemy_names=("Chlora","Dixie","Jenny","Kreenk Ld","Lord Oon Ld","Kati","Yang Luhan","Yoshito")
        for own_name in our_names:
            for enemy_name in enemy_names:
                a=catalog.identify(own_name,True)
                b=catalog.identify(enemy_name,True)
                for leader in (0,1):
                    s=State((Player((a,a),life=15),Player((b,b),life=15)),leader=leader,day=True)
                    for paid in (0,1,3):
                        after=resolve(s,Move(0,paid),Move(0,paid))
                        self.assertEqual(after.round,2)
