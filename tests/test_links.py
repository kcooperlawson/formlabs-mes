"""Every navigation target in the app points at a file that exists.

`st.page_link` raises `StreamlitPageNotFoundError` when its target is missing,
and because the navigation is rendered near the top of each page, that one call
takes the entire screen down - not a broken link, a blank page with a stack
trace on it.

This is not hypothetical. `pages/Admin_Panel.py` linked to
`pages/Device_Registry.py`, which was never written, so the IT Admin console
was dead for every admin who opened it. The page sweep in `test_pages.py` could
not see it: that harness stubs `st.page_link` out, because AppTest runs one
script with no multipage registry behind it. So the check it needs is not
another render - it is reading the source and confirming each target is a real
file, which costs nothing and cannot be fooled by a stub.

It also flags a page that nothing links to. That found a second one: the Theme
Gallery had been built and then left with no route in, reachable only by typing
its URL. Every page in the app is now linked from somewhere, so the exemption
list below is empty - and an entry on it has to still be an exemption, because
a name left there after the page gains a link would go on excusing that page
for ever, including the day something removes its only link.
"""
import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Pages deliberately not in the sidebar. Each is reachable some other way, and
# each is named here so a genuinely stranded page still stands out.
KNOWN_ORPHANS = {
    # Empty on purpose: every page is currently linked from somewhere. Add a
    # page here only with the reason it is reached another way.
}



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
