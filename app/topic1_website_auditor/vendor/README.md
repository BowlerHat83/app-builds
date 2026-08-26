# axe-core drop-in

To switch the WCAG check (Topic 1) over to the real axe-core engine instead
of the built-in custom ruleset, put a copy of the minified axe-core build
in this folder named exactly:

    axe.min.js

Two ways to get it:

1. Easiest - download it directly from the CDN in your own browser:
   https://unpkg.com/axe-core@4.10.2/axe.min.js
   (right-click -> Save As -> axe.min.js, save it into this folder)

2. Via npm, if you have Node installed:
       npm i axe-core
   then copy node_modules/axe-core/axe.min.js into this folder.

That's it - no code changes needed. wcag_service.py checks for this file
on every audit run; if it's here, it uses axe-core and reports
`"engine": "axe-core <version>"` in the results. If it's missing, it
silently falls back to the custom ruleset, exactly like it does today.
