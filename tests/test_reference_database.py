import unittest
from urban_rivals.reference_database import wiki_card, plain, preferred_levels, lookup_reference


def page(text):
    return {"title":"Example","revisions":[{"revid":42,"timestamp":"2026-11-12T00:00:00Z",
            "slots":{"main":{"*":text}}}]}


class ReferenceDatabaseTests(unittest.TestCase):
    def test_empty_fields_do_not_swallow_the_next_level(self):
        card=wiki_card(page("""{{Infobox character
|clan = GHEIST
|ability = +1 [[Life]] per [[Damage]]
|abilitylevel = 4
|level1 = 2/1
|level2 = 3/1
|level3 = 6/1
|level4 = 6/4
|level5 =
}}
"""))
        self.assertEqual([(e['power'],e['damage']) for e in card['levels']],[(2,1),(3,1),(6,1),(6,4)])
        self.assertEqual(card['ability_unlock_level'],4)
        self.assertEqual(card['source']['revision'],42)

    def test_table_cards_can_start_at_level_three(self):
        card=wiki_card(page("""{| class="article-table"
|Clan
|[[Bangers]]
|-
|Ability
|[[Revenge|Revenge: Power +2]]
|-
|Stats lv 3
|8/4 (Ability activated)
|-
|Stats lv 4
|8/5
|-
|Stats lv 5
|8/7
|}
"""))
        self.assertEqual([e['level'] for e in card['levels']],[3,4,5])
        self.assertEqual(card['ability_unlock_level'],3)
        self.assertEqual(card['ability'],'Revenge: Power +2')

    def test_missing_unlock_and_unparsed_stats_are_not_guessed(self):
        card=wiki_card(page("""{{Infobox_character
|clan = Bangers
|ability = Something unknown
|abilitylevel =
|level2 = 4/3 or 7/3
|level3 = 8/4
}}"""))
        self.assertIsNone(card['ability_unlock_level'])
        self.assertIn('error',card['levels'][0])
        self.assertEqual(card['levels'][1]['power'],8)

    def test_prose_is_not_mistaken_for_card_data(self):
        self.assertIsNone(wiki_card(page('An article mentioning 8/4 and an ability.')))
        self.assertEqual(plain('[[Power|Power +2]]'),'Power +2')

    def test_official_level_ability_takes_precedence_over_wiki(self):
        result=lookup_reference("Fixit")
        self.assertEqual(result['preferred_level_source'],'official')
        level=next(e for e in result['preferred_levels']['levels'] if e['level']==4)
        self.assertEqual((level['power'],level['damage']),(7,6))
        self.assertIn('Reprisal',level['ability'])

    def test_known_reference_is_not_reported_as_missing_card_data(self):
        from urban_rivals.vision import Catalog, RecognitionError
        with self.assertRaisesRegex(RecognitionError,'Known reference card'):
            Catalog().identify('Kersten',True,(6,6,4))

    def test_unknown_wiki_unlock_does_not_invent_a_level_ability(self):
        card={'name':'Example','source':{'url':'official'}}
        data={'official_evolution_pages':[], 'wiki_candidates':[
            {'name':'Example','ability':'Power +2','bonus':'','ability_unlock_level':None,
             'levels':[{'level':2,'power':5,'damage':3}],'source':{'url':'wiki'}}]}
        result=preferred_levels(data,card)
        self.assertIsNone(result['levels'][0]['ability'])
        self.assertEqual(result['source_kind'],'wiki_candidate')
