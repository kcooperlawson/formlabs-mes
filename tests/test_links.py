"""Every navigation target in the app points at a file that exists.

`st.page_link` raises `StreamlitPageNotFoundError` when its target is missing,
and because the navigation is rendered near the top of each page, that one call
takes the entire screen down - not a broken link, a blank page with a stack
trace on it.

This is not hypothetical. The IT Admin console was dead for every admin who
opened it, because it linked to a page that was not present in `pages/` at the
time. The page sweep in `test_pages.py` could not see it: that harness stubs
`st.page_link` out, because AppTest runs one script with no multipage registry
behind it. So the check it needs is not another render - it is reading the
source and confirming each target is a real file, which costs nothing and
cannot be fooled by a stub.

It also flags a page that nothing links to. That found the Theme Gallery, built
and then left with no route in, reachable only by typing its URL. Anything
genuinely meant to be unreachable goes on the exemption list below with its
reason - and an entry has to still be an exemption, because a name left there
after the page gains a link would go on excusing that page for ever, including
the day something removes its only link.

A page's link to itself does not count as a route in. Every page renders the
navigation row, so most of them name themselves in it; counting that would let
a page with no way in look linked - which is exactly the case the orphan check
exists to catch.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Pages deliberately not in the sidebar. Each is reachable some other way, and
# each is named here so a genuinely stranded page still stands out.
KNOWN_ORPHANS = set()
# The Device Gateway screen used to be listed here as an orphan on purpose. It
# is linked now, from the Manager Cockpit and IT Admin sidebars, behind the
# Plant Settings switch that turns the gateway on. The reason it was unlinked
# has not changed - the gateway has never run against real equipment - but a
# switch that defaults to off says that better than a missing link did.



# Only the app. The screenshot and debug scripts are development tools; a
# stale path in one of those annoys nobody but me.
def app_sources():
    out = [ROOT / "Home.py", ROOT / "ui_shell.py"]
    out += sorted(ROOT.glob("pages/*.py"))
    return [p for p in out if p.exists()]


FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def targets_in(path):
    """Every literal page path handed to page_link or switch_page in a file."""
    src = path.read_text(encoding="utf-8", errors="replace")
    found = []
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        check(False, f"{path.name} does not parse: {e}")
        return found
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name not in ("page_link", "switch_page"):
            continue
        for arg in node.args[:1]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.append((arg.value, node.lineno))
    return found


def main():
    print("=" * 62)
    print("NAVIGATION TARGETS")
    print("=" * 62)

    linked = set()
    total = 0
    for path in app_sources():
        rel = path.relative_to(ROOT).as_posix()
        for target, line in targets_in(path):
            total += 1
            # A page naming itself in its own navigation row is not a way in.
            # Counting it would have let the Device Gateway screen - which
            # links to itself on line 71 and is linked from nowhere else -
            # register as reachable, which is the precise failure the orphan
            # check below exists to catch.
            if target != rel:
                linked.add(target)
            exists = (ROOT / target).is_file()
            check(exists, f"{rel}:{line} links to {target}, which does not exist")
    print(f"  {total} navigation targets across {len(app_sources())} files, "
          f"{len(linked)} distinct")

    # A .py file dropped into pages/ becomes a real page in Streamlit's own
    # menu whether or not the app links to it, so an unexpected one is worth
    # seeing.
    print("\n  pages nothing links to")
    orphans = []
    for p in sorted(ROOT.glob("pages/*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel not in linked:
            orphans.append(rel)
    unexpected = [o for o in orphans if o not in KNOWN_ORPHANS]
    for o in orphans:
        print(f"    {o}" + ("" if o in KNOWN_ORPHANS else "   <- not a known orphan"))
    if not orphans:
        print("    none")
    check(not unexpected,
          f"unlisted orphan page(s): {unexpected}" if unexpected else "")

    # An exemption has to still be an exemption. A name left on this list
    # after the page gained a link is not harmless: it goes on excusing that
    # page for ever, so the day something removes its only link, nothing says
    # so. The first version of this file listed twelve pages that were all
    # linked from the Manager Cockpit, which would have hidden exactly that.
    for rel in sorted(KNOWN_ORPHANS):
        if not (ROOT / rel).is_file():
            check(False, f"KNOWN_ORPHANS lists {rel}, which is no longer in the repo")
        elif rel in linked:
            check(False, f"KNOWN_ORPHANS lists {rel}, but something links to it now "
                         f"- drop it from the list so it is checked like the rest")

    # --- no link an operator can see leads somewhere they get sent back from --
    #
    # The SCADA page is manager and admin only, and an operator who opens it is
    # sent straight back to their form. So a link to it inside a branch an
    # operator reaches is not a permission problem, it is a button that does
    # nothing, and it reads as the app being broken.
    #
    # This got out twice. Six navigation bars are written by hand, the door was
    # changed in one place, and four of the bars went on offering the link. The
    # rule this asserts is the cheap one: every link to Home.py has to sit
    # inside a branch that tested who is looking.
    print("\n  Links to the plant dashboard are guarded")
    GUARDS = ("role_can_view_scada", "can_view_scada", "role_can_administer",
              "manager", "admin")
    for path in app_sources():
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        # A page that turns an operator away at its own door cannot offer them
        # a link at all, so it is exempt as a whole: a role test whose body
        # stops the script or sends them somewhere else.
        def _is_gate(node):
            if not isinstance(node, ast.If):
                return False
            test_src = ast.get_source_segment(src, node.test) or ""
            if not any(g in test_src for g in GUARDS):
                return False
            body_src = "\n".join(ast.get_source_segment(src, s) or "" for s in node.body)
            return "st.stop()" in body_src or "switch_page" in body_src
        if any(_is_gate(node) for node in ast.walk(tree)):
            continue
        # Every line that is inside the test or body of an `if` whose test
        # mentions one of the guards above.
        guarded = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.If):
                continue
            test_src = ast.get_source_segment(src, node.test) or ""
            if not any(g in test_src for g in GUARDS):
                continue
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    guarded.add(child.lineno)
        for target, lineno in targets_in(path):
            if target != "Home.py":
                continue
            # switch_page("Home.py") is a redirect, not an offer.
            line = src.splitlines()[lineno - 1]
            if "switch_page" in line:
                continue
            check(lineno in guarded,
                  f"{path.name}:{lineno} offers the plant dashboard without "
                  f"checking who is looking")
    print("    checked every page_link to Home.py")

    print("\n" + "=" * 62)
    if FAILS:
        print(f"{len(FAILS)} of {CHECKS} NAVIGATION CHECKS FAILED:")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print(f"ALL {CHECKS} NAVIGATION ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
