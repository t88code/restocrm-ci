"""Тесты scripts/process-checks.sh: временный git-репозиторий, реальные вызовы скрипта."""
import os
import subprocess
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "process-checks.sh")
ENV = dict(
    os.environ,
    GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
    GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null",
)


def run(args, cwd):
    p = subprocess.run(["bash", SCRIPT] + args, cwd=cwd, env=ENV,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


class RepoCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.repo = self._tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("README.md", "base\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(RC-1): base")
        self.base = self.rev()

    def git(self, *args):
        r = subprocess.run(["git"] + list(args), cwd=self.repo, env=ENV,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def rev(self):
        return self.git("rev-parse", "HEAD")

    def write(self, name, content="x\n"):
        path = os.path.join(self.repo, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(content)

    def commit(self, message, name=None):
        self.write(name or "f%d.txt" % len(os.listdir(self.repo)), "c\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.rev()


class PrTitleTest(RepoCase):
    def check(self, title):
        return run(["pr-title", title], self.repo)[0]

    def test_ok_plain(self):
        self.assertEqual(self.check("feat(RC-1): x"), 0)

    def test_ok_bang_before_scope(self):
        self.assertEqual(self.check("feat!(RC-1): x"), 0)

    def test_ok_bang_after_scope(self):
        self.assertEqual(self.check("feat(RC-1)!: x"), 0)

    def test_ok_several_rc(self):
        self.assertEqual(self.check("fix(RC-1,RC-2): x"), 0)

    def test_ok_several_rc_with_space(self):
        self.assertEqual(self.check("fix(RC-1, RC-2): x"), 0)

    def test_no_scope(self):
        code, out = run(["pr-title", "feat: x"], self.repo)
        self.assertEqual(code, 1)
        self.assertIn("<тип>(RC-N)", out)
        self.assertIn("refactor", out)
        self.assertIn("::error", out)

    def test_uppercase_type(self):
        self.assertEqual(self.check("Feat(RC-1): x"), 1)

    def test_free_text(self):
        self.assertEqual(self.check("update"), 1)

    def test_empty_description(self):
        self.assertEqual(self.check("feat(RC-1): "), 1)


class CommitsTest(RepoCase):
    def test_all_with_rc(self):
        self.commit("feat(RC-2): a")
        self.commit("fix(RC-3): b")
        code, _ = run(["commits", self.base, self.rev()], self.repo)
        self.assertEqual(code, 0)

    def test_one_without_rc(self):
        self.commit("feat(RC-2): a")
        bad = self.commit("просто правка")
        code, out = run(["commits", self.base, self.rev()], self.repo)
        self.assertEqual(code, 1)
        self.assertIn(bad[:8], out)
        self.assertIn("просто правка", out)

    def test_revert_ok(self):
        self.commit('Revert "x"')
        code, _ = run(["commits", self.base, self.rev()], self.repo)
        self.assertEqual(code, 0)

    def test_fixup_ok(self):
        self.commit("fixup! feat(RC-2): a")
        code, _ = run(["commits", self.base, self.rev()], self.repo)
        self.assertEqual(code, 0)

    def test_merge_commits_not_checked(self):
        self.git("checkout", "-q", "-b", "side")
        self.commit("feat(RC-2): side")
        self.git("checkout", "-q", "main")
        self.commit("feat(RC-3): main-side")
        self.git("merge", "-q", "--no-ff", "side", "-m", "Merge side without number")
        code, out = run(["commits", self.base, self.rev()], self.repo)
        self.assertEqual(code, 0, out)


class DivergedMainTest(RepoCase):
    """main ушёл вперёд после ответвления ветки PR: чужие коммиты main не проверяются."""

    def setUp(self):
        super().setUp()
        self.git("checkout", "-q", "-b", "pr")
        self.commit("feat(RC-2): в ветке PR", "pr.txt")
        self.pr_head = self.rev()
        self.git("checkout", "-q", "main")
        self.commit("чужой коммит без номера", "other.txt")
        self.commit("чужой коммит с секретом", ".env")
        self.main_tip = self.rev()

    def test_commits_ignore_main_commits(self):
        code, out = run(["commits", self.main_tip, self.pr_head], self.repo)
        self.assertEqual(code, 0, out)
        self.assertIn("проверено: 1", out)

    def test_commits_still_catch_bad_pr_commit(self):
        self.git("checkout", "-q", "pr")
        bad = self.commit("без номера в PR", "pr2.txt")
        code, out = run(["commits", self.main_tip, bad], self.repo)
        self.assertEqual(code, 1)
        self.assertIn(bad[:8], out)

    def test_secrets_ignore_main_files(self):
        code, out = run(["secrets", self.main_tip, self.pr_head], self.repo)
        self.assertEqual(code, 0, out)


class SecretsTest(RepoCase):
    def check(self):
        return run(["secrets", self.base, self.rev()], self.repo)

    def test_added_env(self):
        self.commit("feat(RC-2): a", ".env")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn(".env", out)

    def test_added_nested_key_file(self):
        self.commit("feat(RC-2): a", "deploy/server.pem")
        code, out = self.check()
        self.assertEqual(code, 1)
        self.assertIn("deploy/server.pem", out)

    def test_example_ok(self):
        self.commit("feat(RC-2): a", "appsettings.Example.json")
        self.assertEqual(self.check()[0], 0)

    def test_env_example_ok(self):
        self.commit("feat(RC-2): a", ".env.example")
        self.assertEqual(self.check()[0], 0)

    def test_modified_existing_ok(self):
        # appsettings.json уже отслеживается в базе: правка — не добавление.
        self.write("appsettings.json", "{}\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "chore(RC-1): tracked config")
        self.base = self.rev()
        self.write("appsettings.json", '{"a":1}\n')
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feat(RC-2): edit")
        self.assertEqual(self.check()[0], 0)


if __name__ == "__main__":
    unittest.main()
