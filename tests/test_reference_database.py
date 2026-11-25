import unittest
from urban_rivals.reference_database import (
    compare_source_levels, day_night_variants, lookup_reference, plain,
    preferred_levels, reconcile_reference, wiki_card,
)


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
            Catalog().identify('Masbulla',True,(7,7,5))

    def test_unknown_wiki_unlock_does_not_invent_a_level_ability(self):
        card={'name':'Example','source':{'url':'official'}}
        data={'official_evolution_pages':[], 'wiki_candidates':[
            {'name':'Example','ability':'Power +2','bonus':'','ability_unlock_level':None,
             'levels':[{'level':2,'power':5,'damage':3}],'source':{'url':'wiki'}}]}
        result=preferred_levels(data,card)
        self.assertIsNone(result['levels'][0]['ability'])
        self.assertEqual(result['source_kind'],'wiki_candidate')

    def test_day_and_night_abilities_are_preserved_as_variants(self):
        self.assertEqual(day_night_variants(
            'Day: Cancel Opp. Power Modif.',
            'Night: -2 Opp Power, Min 6'),{
                'day':'Day: Cancel Opp. Power Modif.',
                'night':'Night: -2 Opp Power, Min 6'})
        self.assertEqual(day_night_variants('Power +2','Night: Power +2'),{})

        card={'name':'Example','clan':'Junkz','source':{'url':'official'}}
        data={'official_evolution_pages':[{'url':'official','levels':[
                  {'name':'Example','clan':'Junkz','level':3,'power':7,'damage':5,
                   'ability':'Night: Power +2','ability_unlock_level':None,'bonus':'Attack +8'}]}],
              'wiki_candidates':[], 'conditional_bonuses':{},
              'conditional_abilities':{'official':{
                  'day':'Day: Cancel Opp. Power Modif.','night':'Night: Power +2'}}}
        level=preferred_levels(data,card)['levels'][0]
        self.assertEqual(level['ability_variants']['day'],'Day: Cancel Opp. Power Modif.')

    def test_reconciliation_fails_closed_on_missing_official_field(self):
        maximum={'name':'Example','clan':'Junkz','level':2,'power':7,'damage':4,
                 'ability':'Power +2','bonus':'Attack +8','source':{'url':'official'}}
        row={'name':'Example','clan':'Junkz','level':2,'power':7,'damage':4,
             'ability':'','ability_unlock_level':None,'bonus':'Attack +8'}
        data={'official_maximum_levels':[maximum],
              'official_evolution_pages':[{'url':'official','levels':[row]}],
              'conditional_bonuses':{},'conflicts':[]}
        result=reconcile_reference(data)
        self.assertFalse(result['complete'])
        self.assertEqual(result['missing_or_invalid_fields'],{'ability':1})

    def test_source_comparison_resolves_to_official_rows(self):
        maximum={'name':'Example','clan':'Junkz','level':2,'power':7,'damage':4,
                 'ability':'Power +2','bonus':'Attack +8','source':{'url':'official'}}
        official={'url':'official','levels':[{
            'name':'Example','clan':'Junkz','level':2,'power':7,'damage':4,
            'ability':'Power +2','ability_unlock_level':None,'bonus':'Attack +8'}]}
        wiki={'name':'Example','clan':'Junkz','ability':'Power +1','bonus':'Attack +8',
              'ability_unlock_level':2,'levels':[{'level':2,'power':6,'damage':4}],
              'source':{'url':'wiki'}}
        result=compare_source_levels({'official_maximum_levels':[maximum],
            'official_evolution_pages':[official],'wiki_candidates':[wiki]})[0]
        self.assertTrue(result['resolved'])
        self.assertEqual(result['decision'],'prefer_official_evolution_table')
        self.assertIn('field_difference',{d['kind'] for d in result['differences']})
