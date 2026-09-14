"""Operator_Form.py, split into one module per tab.

pages/Operator_Form.py got past 2,000 lines with every tab (Pouring,
Packing, Downtime, Audit, Notes) plus the page chrome (auth, sidebar,
daily checklist gate, active-run cards) living in one file. That made
even a small, well-understood change - like converting the Downtime tab
to a plain st.form so it stops rerunning the whole page on every
keystroke - something that had to be done carefully to avoid disturbing
whatever else happened to be sitting nearby in the same file.

This package holds one module per tab (pouring_tab.py, packing_tab.py,
downtime_tab.py, audit_tab.py, notes_tab.py), plus:

  - shared.py     - small helpers used by more than one place
                     (_vessel_label, _display_lot, bulk_vessel_state,
                     the Lottie/logo loaders)
  - checklist.py  - the daily startup checklist gate, which is large,
                     self-contained, and the single riskiest block on
                     this page to get wrong (it is what stands between
                     an operator and the terminal each shift)

Page-level chrome that only ever happens once per render - theme
injection, the sidebar, today's stats, the active-run cards, the resin
lookup reference, the tank reconciliation tool, and the tab container
itself - stays in pages/Operator_Form.py. Each tab module exposes a
single render(ctx) function; ctx is a plain namespace of the request-
scoped values (current_user, current_shift, active_pumps, df_runs, the
resin colour map, ...) that more than one tab needs, built once in
Operator_Form.py and passed down rather than re-derived in each module.
"""
