import tempfile
import unittest
import zipfile
from pathlib import Path
from src.data import load_population, load_existing, make_city_problem


class TestPublicDataParsers(unittest.TestCase):
    def test_csv_and_zip_with_city_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            csv = root / "geodae.csv"
            csv.write_text("c_com_insee;c_lat_coor1;c_long_coor1\n"
                           "34172;43.610;3.880\n"
                           "34172;43.620;3.890\n"
                           "75056;48.850;2.350\n", encoding="utf-8")
            zi = root / "insee.zip"
            data = ("idcar_200m;lcog_geo;ind\n"
                    "CRS3035RES200mN2325000E3821000;34172;100\n"
                    "CRS3035RES200mN2325200E3821200;34172;150\n"
                    "CRS3035RES200mN2300000E3800000;75056;80\n")
            with zipfile.ZipFile(zi, "w") as archive:
                archive.writestr("carreaux_200m_test.csv", data)
            pop_points, pop = load_population(zi, "34172")
            existing = load_existing(csv, "34172")
            self.assertEqual(len(pop), 2)
            self.assertEqual(pop.sum(), 250)
            self.assertEqual(len(existing), 2)
            self.assertEqual(pop_points.shape, (2, 2))
            instance = make_city_problem("34172", "Montpellier test", 350, 2,
                                         geodae_csv=csv, insee_zip=zi)
            self.assertEqual(len(instance.population), 2)
            self.assertEqual(len(instance.candidates_xy), 2)


if __name__ == "__main__":
    unittest.main()
