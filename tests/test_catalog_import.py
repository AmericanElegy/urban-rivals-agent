import json
from pathlib import Path
import tempfile
import unittest
from urban_rivals.catalog_import import merge_official_records
from urban_rivals.vision import Catalog,RecognitionError


class CatalogImportTests(unittest.TestCase):
    def fixture(self):
        return {"schema":"urban-rivals/cards/v1","cards":[{"name":"Test","power":7,"damage":6,"stars":4,"clan":"Bangers","ability":"Reprisal: Protection: Power And Damage","bonus":"Power +2"}]}

    def record(self,**changes):
        return dict(self.fixture()["cards"][0],url="https://www.urban-rivals.com/game/characters/?id_perso=1",**changes)

    def test_adds_exact_level_without_overwriting_reference(self):
        record=self.record()
        record.update(stars=5,ability="Protection: Power And Damage")
        merged,audit=merge_official_records(self.fixture(),[record])
        self.assertEqual(audit[0]["result"],"added")
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/"catalog.json";p.write_text(json.dumps(merged))
            catalog=Catalog(p)
            self.assertEqual(catalog.identify("Test",True).stars,4)
            self.assertEqual(catalog.identify("Test",True,(7,6,5)).ability[0].condition,"always")
            self.assertEqual(catalog.identify("Test",True,(7,6,4)).ability[0].condition,"reprisal")
            with self.assertRaises(RecognitionError):catalog.identify("Test",True,(7,6,3))

    def test_unsupported_or_conflicting_text_is_quarantined(self):
        unsupported=self.record();unsupported.update(name="Poison card",ability="Poison 2, Min 1")
        conflict=self.record();conflict["ability"]="Power +8"
        merged,audit=merge_official_records(self.fixture(),[unsupported,conflict])
        self.assertEqual(len(merged["cards"]),1)
        self.assertEqual([entry["result"] for entry in audit],["rejected","rejected"])

    def test_nonofficial_url_and_missing_stats_are_rejected(self):
        wrong=self.record();wrong["url"]="https://example.test/card/1"
        missing=self.record();missing.pop("stars")
        _,audit=merge_official_records(self.fixture(),[wrong,missing])
        self.assertTrue(all(e["result"]=="rejected" for e in audit))

    def test_import_is_idempotent_and_reference_fixit_is_preserved(self):
        catalog=Catalog()
        self.assertEqual(catalog.identify("Fixit",True,(7,6,4)).ability[0].condition,"reprisal")
        self.assertEqual(catalog.identify("Fixit",True,(7,6,5)).ability[0].condition,"always")
        source=json.loads(Path("urban_rivals/data/official_bangers_import.json").read_text())
        records=[entry.get("card",entry.get("record")) for entry in source["entries"]]
        for record,entry in zip(records,source["entries"]):record["url"]=entry["source"]
        data=json.loads(Path("urban_rivals/data/training_cards.json").read_text())
        merged,audit=merge_official_records(data,records)
        self.assertEqual(len(merged["cards"]),len(data["cards"]))
        self.assertFalse(any(e["result"]=="added" for e in audit))

    def test_full_public_import_is_complete_and_idempotent(self):
        source=json.loads(Path("urban_rivals/data/official_catalog_import.json").read_text())
        self.assertEqual(len(source["entries"]),2507)
        self.assertEqual(len({e["source"] for e in source["entries"]}),2507)
        records=[]
        for entry in source["entries"]:
            record=dict(entry.get("card",entry.get("record")))
            record["url"]=entry["source"]
            records.append(record)
        data=json.loads(Path("urban_rivals/data/training_cards.json").read_text())
        merged,audit=merge_official_records(data,records)
        self.assertEqual(merged,data)
        self.assertFalse(any(e["result"]=="added" for e in audit))

    def test_bulk_import_cannot_enable_special_clan_rules(self):
        records=[]
        for clan in ("GhosTown","Leader","Oculus"):
            record=self.record();record.update(name=clan,clan=clan,ability="No Ability",bonus="No Bonus")
            records.append(record)
        merged,audit=merge_official_records(self.fixture(),records)
        self.assertEqual(len(merged["cards"]),1)
        self.assertTrue(all(e["result"]=="rejected" for e in audit))
