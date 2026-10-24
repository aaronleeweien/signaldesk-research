"""UI-only tests: every research page must answer simply BEFORE showing numbers."""
import unittest
import pathlib
import re
import shutil
import subprocess
import tempfile
from research.simplify_archive_pages import COPY,simplify_document

ROOT=pathlib.Path(__file__).resolve().parents[1]
PAGES={
    "decision_template.html":("easy-invest","easy-trade"),
    "established_template.html":("easy-est","easy-estaction"),
    "factor_template.html":("easy-factor","easy-factoraction"),
    "forward_template.html":("easy-forward","easy-forwardaction"),
    "scanner_template.html":("easy-scanner","easy-scanneraction"),
    "validation_template.html":("easy-validation","easy-validationaction"),
    "stock_template.html":("easy-stock","easy-stockaction"),
    "institutional_template.html":("easy-institutional","easy-institutionalaction"),
    "lab_template.html":("easy-lab","easy-labaction")
}
class BeginnerDashboardTests(unittest.TestCase):
    def test_all_main_pages_explain_conclusion_and_action_before_tables(self):
        for name,(answer,action) in PAGES.items():
            with self.subTest(page=name):
                page=(ROOT/"research"/name).read_text(encoding="utf-8")
                self.assertIn('class="easy-wrap"',page)
                self.assertIn(f'id="{answer}"',page)
                self.assertIn(f'id="{action}"',page)
                self.assertIn("What should I do?",page)
                self.assertIn("Jargon:",page)
                self.assertTrue(page.index('class="easy-wrap"')<page.index("<table") if "<table" in page else True)
                if name != "decision_template.html":
                    self.assertIn("decisions.html",page)

    def test_copy_preserves_historical_numbers_and_code(self):
        html='<!doctype html><html><head></head><body><main><h1>Original</h1><script>const returns = 11.23;</script></main></body></html>'
        for name,info in COPY.items():
            with self.subTest(page=name):
                new=simplify_document(html,info)
                self.assertIn("const returns = 11.23;",new)
                self.assertIn("Original",new)
                self.assertIn("What should I do?",new)
                self.assertEqual(new,simplify_document(new,info))

    def test_js_syntax_in_all_main_templates(self):
        if not shutil.which("node"):self.skipTest("node is not available")
        for name in PAGES:
            page=(ROOT/"research"/name).read_text(encoding="utf-8")
            scripts=re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>",page,flags=re.I|re.S)
            executable=[body for body in scripts if "(function" in body or "(()=>{" in body]
            with self.subTest(page=name):
                self.assertGreaterEqual(len(executable),1)
                for i,script in enumerate(executable):
                    with tempfile.TemporaryDirectory() as tmp:
                        target=pathlib.Path(tmp)/"test.js"
                        target.write_text(script,encoding="utf-8")
                        command=subprocess.run(["node","--check",str(target)],capture_output=True,text=True)
                        self.assertEqual(command.returncode,0,
                            f"{name}, script {i}: {command.stderr}")
if __name__=="__main__":unittest.main()
