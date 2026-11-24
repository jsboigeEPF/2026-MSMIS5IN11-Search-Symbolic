import unittest
import numpy as np
from src.problem import CoverageProblem, make_demo, make_small_benchmark
from src.algorithms import greedy, genetic, simulated_annealing, exact_ilp


class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.p = CoverageProblem(
            demand_xy=[[0, 0], [100, 0], [1000, 0], [1100, 0]],
            population=[10, 20, 30, 40],
            candidates_xy=[[0, 0], [1000, 0], [1100, 0]],
            existing_xy=[[0, 0]], radius_m=150)

    def test_initial_population_not_double_counted(self):
        self.assertEqual(self.p.initial_score, 30)
        self.assertEqual(self.p.score([0]), 30)
        self.assertEqual(self.p.score([1]), 100)
        self.assertEqual(self.p.score([1, 2]), 100)

    def test_greedy(self):
        r = greedy(self.p, 1)
        self.assertTrue(self.p.verify(r.selected, 1))
        self.assertEqual(r.score, 100)

    def test_reject_duplicate(self):
        with self.assertRaises(ValueError):
            self.p.verify((1, 1), 2)

    def test_metheuristics_meet_constraints_and_not_worse_than_greedy(self):
        p = make_demo(seed=8)
        greedy_result = greedy(p, 4)
        for r in [genetic(p, 4, seed=8, generations=15, population_size=15),
                  simulated_annealing(p, 4, seed=8, iterations=100)]:
            self.assertTrue(p.verify(r.selected, 4))
            self.assertGreaterEqual(r.score, greedy_result.score)

    def test_exact_milp(self):
        r = exact_ilp(self.p, 1)
        self.assertTrue(self.p.verify(r.selected, 1))
        self.assertEqual(r.score, 100)

    def test_exact_dominates_on_small_benchmark(self):
        p = make_small_benchmark()
        exact = exact_ilp(p, 3)
        self.assertGreaterEqual(exact.score + 1e-6, greedy(p, 3).score)


if __name__ == "__main__":
    unittest.main()
