import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class GenerationContractTests(unittest.TestCase):
    def test_instrumental_plan_has_a_complete_form(self):
        source = (ROOT / "python" / "main.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        value = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "INSTRUMENTAL_LYRICS" for target in node.targets)
        )
        self.assertIn("[Intro]", value)
        self.assertIn("[Chorus]", value)
        self.assertIn("[Outro]", value)
        self.assertGreaterEqual(value.count("[Instrumental]"), 4)

    def test_reuse_as_new_song_requests_a_random_seed(self):
        app = (ROOT / "src" / "App.tsx").read_text(encoding="utf-8")
        reuse = app.split("function reuseSong", 1)[1].split("async function saveSongDetails", 1)[0]
        self.assertIn('setLockedSeed("")', reuse)
        self.assertNotIn("setLockedSeed(String(song.seed))", reuse)


if __name__ == "__main__":
    unittest.main()
