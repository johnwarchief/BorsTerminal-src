# خروجیِ `python scripts/build_all.py` (BUILD_EXIT=0)

npm run build + PyInstaller رویِ `venv_build/`؛ انتهایِ لاگ اندازه و مسیرِ خروجی را می‌دهد.

```

> bors-terminal-frontend@1.0.86 build
> vite build

[36mvite v5.4.21 [32mbuilding for production...[36m[39m
transforming...
node_modules/zod/v4/core/regexes.js (72:0): A comment

"/** Anchors a pattern source. The interpolation lives here rather than at the call site because
 * esbuild will not drop a `@__PURE__` call whose own argument interpolates a variable, but it
 * will drop `anchor(dateSource)`. Keeping it inline pinned `date` into every bundle. */"

in "node_modules/zod/v4/core/regexes.js" contains an annotation that Rollup cannot interpret due to the position of the comment. The comment will be removed to avoid issues.
node_modules/zod/v4/core/util.js (400:0): A comment

"// Wrapped in a `@__PURE__` IIFE: esbuild never tree-shakes a top-level initializer that contains a member access on `Number`, so the bare object literal survived into every bundle."

in "node_modules/zod/v4/core/util.js" contains an annotation that Rollup cannot interpret due to the position of the comment. The comment will be removed to avoid issues.
[32m✓[39m 735 modules transformed.
rendering chunks...
computing gzip size...
[2mdist/[22m[32mindex.html                                    [39m[1m[2m  0.48 kB[22m[1m[22m[2m │ gzip:   0.34 kB[22m
[2mdist/[22m[32massets/indicator.worker-Bl64aN4W.js           [39m[1m[2m 42.47 kB[22m[1m[22m
[2mdist/[22m[35massets/TechnicalPage-DB544epO.css             [39m[1m[2m  2.99 kB[22m[1m[22m[2m │ gzip:   0.77 kB[22m
[2mdist/[22m[35massets/KLineChartWrapper-b6TxNGhU.css         [39m[1m[2m 12.16 kB[22m[1m[22m[2m │ gzip:   2.76 kB[22m
[2mdist/[22m[35massets/index-BmP4r4Z6.css                     [39m[1m[2m139.42 kB[22m[1m[22m[2m │ gzip:  20.38 kB[22m
[2mdist/[22m[36massets/signalBus-2dwDTV_P.js                  [39m[1m[2m  0.15 kB[22m[1m[22m[2m │ gzip:   0.13 kB[22m
[2mdist/[22m[36massets/index-Bp4XlgoD.js                      [39m[1m[2m  0.34 kB[22m[1m[22m[2m │ gzip:   0.25 kB[22m
[2mdist/[22m[36massets/EmptyState-vjHeETdP.js                 [39m[1m[2m  0.41 kB[22m[1m[22m[2m │ gzip:   0.27 kB[22m
[2mdist/[22m[36massets/levels-DXqKsBvM.js                     [39m[1m[2m  0.64 kB[22m[1m[22m[2m │ gzip:   0.56 kB[22m
[2mdist/[22m[36massets/tvIndicators-Cv4iCyCv.js               [39m[1m[2m  0.70 kB[22m[1m[22m[2m │ gzip:   0.44 kB[22m
[2mdist/[22m[36massets/watchSymbolsStore-6FqXFcdn.js          [39m[1m[2m  0.75 kB[22m[1m[22m[2m │ gzip:   0.44 kB[22m
[2mdist/[22m[36massets/useIndustries-QI2s-r-_.js              [39m[1m[2m  0.96 kB[22m[1m[22m[2m │ gzip:   0.51 kB[22m
[2mdist/[22m[36massets/WatchlistStar-Bp8mUXUV.js              [39m[1m[2m  0.97 kB[22m[1m[22m[2m │ gzip:   0.58 kB[22m
[2mdist/[22m[36massets/tvTools-uIDBnoVf.js                    [39m[1m[2m  1.15 kB[22m[1m[22m[2m │ gzip:   0.77 kB[22m
[2mdist/[22m[36massets/Collapse-BIFmEn_A.js                   [39m[1m[2m  1.65 kB[22m[1m[22m[2m │ gzip:   0.80 kB[22m
[2mdist/[22m[36massets/DownloadRowsButton-BVIW57T-.js         [39m[1m[2m  1.96 kB[22m[1m[22m[2m │ gzip:   1.19 kB[22m
[2mdist/[22m[36massets/userWatchlist-D1_m-ocH.js              [39m[1m[2m  2.21 kB[22m[1m[22m[2m │ gzip:   1.22 kB[22m
[2mdist/[22m[36massets/useNnData-BQE9u7dJ.js                  [39m[1m[2m  2.39 kB[22m[1m[22m[2m │ gzip:   1.23 kB[22m
[2mdist/[22m[36massets/StrategyTreeStepper-Bs4YXaFc.js        [39m[1m[2m  3.16 kB[22m[1m[22m[2m │ gzip:   1.41 kB[22m
[2mdist/[22m[36massets/ftsLabels-_2dhetHO.js                  [39m[1m[2m  5.72 kB[22m[1m[22m[2m │ gzip:   1.79 kB[22m
[2mdist/[22m[36massets/NotificationsPage-ByAnQWW7.js          [39m[1m[2m  7.62 kB[22m[1m[22m[2m │ gzip:   2.98 kB[22m
[2mdist/[22m[36massets/KLineChartsEngine-KyokgW1p.js          [39m[1m[2m  9.58 kB[22m[1m[22m[2m │ gzip:   3.65 kB[22m
[2mdist/[22m[36massets/TapeTable-z4NJfLo5.js                  [39m[1m[2m 12.93 kB[22m[1m[22m[2m │ gzip:   5.19 kB[22m
[2mdist/[22m[36massets/EngineLabPage-DPBwRzlB.js              [39m[1m[2m 15.10 kB[22m[1m[22m[2m │ gzip:   5.70 kB[22m
[2mdist/[22m[36massets/mabnaIndicators-Bjce0IeZ.js            [39m[1m[2m 16.76 kB[22m[1m[22m[2m │ gzip:   5.73 kB[22m
[2mdist/[22m[36massets/FtsSettingsDrawer-WkPmNYrQ.js          [39m[1m[2m 23.48 kB[22m[1m[22m[2m │ gzip:   8.33 kB[22m
[2mdist/[22m[36massets/WatchMarketWorkspace-jA30D6RB.js       [39m[1m[2m 27.75 kB[22m[1m[22m[2m │ gzip:   9.15 kB[22m
[2mdist/[22m[36massets/SymbolSelectBox-B-jbH_SW.js            [39m[1m[2m 27.88 kB[22m[1m[22m[2m │ gzip:   8.86 kB[22m
[2mdist/[22m[36massets/chunk-QVJHXQ4A-DLNF0_nK.js             [39m[1m[2m 31.85 kB[22m[1m[22m[2m │ gzip:   9.26 kB[22m
[2mdist/[22m[36massets/MarketPage-vGkfI1K2.js                 [39m[1m[2m 35.54 kB[22m[1m[22m[2m │ gzip:  11.10 kB[22m
[2mdist/[22m[36massets/priceAlerts-D09QWm-c.js                [39m[1m[2m 36.23 kB[22m[1m[22m[2m │ gzip:  12.27 kB[22m
[2mdist/[22m[36massets/StrategyTreePage-DMqU2D6f.js           [39m[1m[2m 52.34 kB[22m[1m[22m[2m │ gzip:  16.44 kB[22m
[2mdist/[22m[36massets/PortfolioPage-D3hE9nA3.js              [39m[1m[2m 57.41 kB[22m[1m[22m[2m │ gzip:  17.48 kB[22m
[2mdist/[22m[36massets/TechnicalPage-D9z9jOXB.js              [39m[1m[2m105.12 kB[22m[1m[22m[2m │ gzip:  32.53 kB[22m
[2mdist/[22m[36massets/KLineChartWrapper-CyV3p7Cw.js          [39m[1m[2m106.91 kB[22m[1m[22m[2m │ gzip:  31.65 kB[22m
[2mdist/[22m[36massets/FundamentalPage-Bwpj_1Mp.js            [39m[1m[2m110.64 kB[22m[1m[22m[2m │ gzip:  33.28 kB[22m
[2mdist/[22m[36massets/MarketStatusPage-CRUJ1bXy.js           [39m[1m[2m131.30 kB[22m[1m[22m[2m │ gzip:  36.73 kB[22m
[2mdist/[22m[36massets/MasterPage-BhPbvdpc.js                 [39m[1m[2m156.64 kB[22m[1m[22m[2m │ gzip:  48.25 kB[22m
[2mdist/[22m[36massets/useCandleFeed-B7-JtnRD.js              [39m[1m[2m240.92 kB[22m[1m[22m[2m │ gzip:  64.03 kB[22m
[2mdist/[22m[36massets/FastFinancialChartsEngine-D2f__ad5.js  [39m[1m[2m296.64 kB[22m[1m[22m[2m │ gzip:  71.88 kB[22m
[2mdist/[22m[36massets/index-BzFJmp4W.js                      [39m[1m[33m612.67 kB[39m[22m[2m │ gzip: 194.66 kB[22m
[33m
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.[39m
[32m✓ built in 19.35s[39m
980 INFO: PyInstaller: 6.22.3, contrib hooks: 2026.7
981 INFO: Python: 3.14.4
1425 INFO: Platform: Windows-11-10.0.28000-SP0
1426 INFO: Python environment: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\venv_build
1433 INFO: Removing temporary files and cleaning cache in C:\Users\Johnkallnaya\AppData\Local\pyinstaller
1442 INFO: Module search paths (PYTHONPATH):
['C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf',
 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\python314.zip',
 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\DLLs',
 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib',
 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314',
 'C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf\\venv_build',
 'C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf\\venv_build\\Lib\\site-packages',
 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages',
 'C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf']
3689 INFO: Appending 'datas' from .spec
3706 INFO: checking Analysis
3707 INFO: Building Analysis because Analysis-00.toc is non existent
3707 INFO: Looking for Python shared library...
3707 INFO: Using Python shared library: C:\Users\Johnkallnaya\AppData\Local\Programs\Python\Python314\python314.dll
3707 INFO: Running Analysis Analysis-00.toc
3707 INFO: Target bytecode optimization level: 0
3707 INFO: Initializing module dependency graph...
3718 INFO: Initializing module graph hook caches...
3989 INFO: Analyzing modules for base_library.zip ...
7027 INFO: Processing standard module hook 'hook-encodings.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
10869 INFO: Processing standard module hook 'hook-math.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
15211 INFO: Processing standard module hook 'hook-difflib.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
15257 INFO: Processing standard module hook 'hook-heapq.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
15655 INFO: Processing standard module hook 'hook-pickle.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
21156 INFO: Caching module dependency graph...
21263 INFO: Analyzing C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\bors_entry.py
21439 INFO: Processing standard module hook 'hook-webbrowser.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
21653 INFO: Processing standard module hook 'hook-sysconfig.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
21667 INFO: Processing standard module hook 'hook-_ctypes.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
22296 INFO: Processing standard module hook 'hook-sqlite3.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
23055 INFO: Processing standard module hook 'hook-pandas.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
27038 INFO: Processing standard module hook 'hook-platform.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
27170 INFO: Processing standard module hook 'hook-numpy.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
28564 INFO: Processing pre-safe-import-module hook 'hook-typing_extensions.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
28568 INFO: SetuptoolsInfo: initializing cached setuptools info...
31158 INFO: Processing standard module hook 'hook-multiprocessing.util.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
31487 INFO: Processing standard module hook 'hook-xml.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
41991 INFO: Processing standard module hook 'hook-charset_normalizer.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
43739 INFO: Processing standard module hook 'hook-zoneinfo.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
49432 INFO: Processing standard module hook 'hook-pandas.io.formats.style.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
58357 INFO: Processing standard module hook 'hook-pandas.plotting.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
60594 INFO: Processing standard module hook 'hook-dateutil.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
61191 INFO: Processing pre-safe-import-module hook 'hook-six.moves.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
64825 INFO: Processing standard module hook 'hook-openpyxl.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65205 INFO: Processing standard module hook 'hook-lxml.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
65995 INFO: Processing standard module hook 'hook-lxml.etree.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
66599 INFO: Processing standard module hook 'hook-xml.etree.cElementTree.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
67762 INFO: Processing standard module hook 'hook-PIL.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
68166 INFO: Processing standard module hook 'hook-PIL.Image.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
69626 INFO: Processing standard module hook 'hook-PIL.ImageFilter.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
74218 INFO: Processing standard module hook 'hook-pandas.io.clipboard.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
74742 INFO: Processing standard module hook 'hook-xml.dom.domreg.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
77132 INFO: Processing standard module hook 'hook-anyio.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
80424 INFO: Processing standard module hook 'hook-pydantic.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
88804 INFO: Processing standard module hook 'hook-uvicorn.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
93123 INFO: Processing standard module hook 'hook-urllib3.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
93586 INFO: Processing pre-safe-import-module hook 'hook-backports.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
93588 INFO: Setuptools: 'backports' appears to be a full setuptools-vendored copy - creating alias to 'setuptools._vendor.backports'!
96725 INFO: Processing standard module hook 'hook-certifi.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
96855 INFO: Processing standard module hook 'hook-chardet.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
97702 INFO: Processing standard module hook 'hook-cryptography.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
100322 INFO: hook-cryptography: cryptography does not seem to be using dynamically linked OpenSSL.
102012 INFO: Processing standard module hook 'hook-webview.py' from 'C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf\\venv_build\\Lib\\site-packages\\webview\\__pyinstaller'
103739 INFO: Processing pre-safe-import-module hook 'hook-gi.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
104214 INFO: Processing standard module hook 'hook-clr.py' from 'C:\\Users\\Johnkallnaya\\Desktop\\Borsterminal\\.worktrees\\system2-perf\\venv_build\\Lib\\site-packages\\pythonnet\\_pyinstaller'
104271 INFO: Processing standard module hook 'hook-clr_loader.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
104678 INFO: Processing standard module hook 'hook-pycparser.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
105226 INFO: Processing pre-safe-import-module hook 'hook-distutils.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
106149 INFO: Analyzing hidden import 'uvicorn.loops.auto'
106158 INFO: Analyzing hidden import 'uvicorn.protocols.http.auto'
106162 INFO: Analyzing hidden import 'uvicorn.protocols.websockets.auto'
106165 INFO: Analyzing hidden import 'uvicorn.lifespan.on'
106196 INFO: Analyzing hidden import 'codal_fetcher'
107934 INFO: Analyzing hidden import 'app'
108049 INFO: Processing standard module hook 'hook-orjson.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
113546 INFO: Processing standard module hook 'hook-docx.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
116840 INFO: Processing standard module hook 'hook-reportlab.lib.utils.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
117363 INFO: Processing standard module hook 'hook-reportlab.pdfbase._fontdata.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
125575 INFO: Analyzing hidden import 'packaging'
125575 INFO: Processing pre-safe-import-module hook 'hook-packaging.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
125580 INFO: Analyzing hidden import 'PIL.ImageDraw'
125942 INFO: Processing module hooks (post-graph stage)...
127367 INFO: Processing standard module hook 'hook-lxml.isoschematron.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
127419 WARNING: Hidden import "pycparser.lextab" not found!
127419 WARNING: Hidden import "pycparser.yacctab" not found!
127842 INFO: Processing pre-safe-import-module hook 'hook-tomli.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\pre_safe_import_module'
127843 INFO: Setuptools: 'tomli' appears to be a setuptools-vendored copy - creating alias to 'setuptools._vendor.tomli'!
129134 INFO: Processing standard module hook 'hook-PIL.SpiderImagePlugin.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks'
129348 INFO: Processing standard module hook 'hook-lxml.objectify.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
129349 INFO: Processing standard module hook 'hook-tzdata.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\stdhooks'
130722 INFO: Performing binary vs. data reclassification (789 entries)
131108 INFO: Looking for ctypes DLLs
131368 INFO: Analyzing run-time hooks ...
131385 INFO: Including run-time hook 'pyi_rth_pkgutil.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
131393 INFO: Including run-time hook 'pyi_rth_multiprocessing.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
131399 INFO: Including run-time hook 'pyi_rth_cryptography_openssl.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\_pyinstaller_hooks_contrib\\rthooks'
131403 INFO: Including run-time hook 'pyi_rth_inspect.py' from 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\PyInstaller\\hooks\\rthooks'
131519 INFO: Creating base_library.zip...
131577 INFO: Looking for dynamic libraries
136713 INFO: Extra DLL search directories (AddDllDirectory): ['C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\numpy.libs', 'C:\\Users\\Johnkallnaya\\AppData\\Local\\Programs\\Python\\Python314\\Lib\\site-packages\\pandas.libs']
136714 INFO: Extra DLL search directories (PATH): []
139277 INFO: Warnings written to C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\build\fts_terminal\warn-fts_terminal.txt
139847 INFO: Graph cross-reference written to C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\build\fts_terminal\xref-fts_terminal.html
140080 INFO: checking PYZ
140080 INFO: Building PYZ because PYZ-00.toc is non existent
140080 INFO: Building PYZ (ZlibArchive) C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\build\fts_terminal\PYZ-00.pyz
143736 INFO: Building PYZ (ZlibArchive) C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\build\fts_terminal\PYZ-00.pyz completed successfully.
144188 INFO: checking PKG
144189 INFO: Building PKG because PKG-00.toc is non existent
144189 INFO: Building PKG (CArchive) BorsTerminal_Ultimate.pkg
144298 INFO: Building PKG (CArchive) BorsTerminal_Ultimate.pkg completed successfully.
144302 INFO: Bootloader C:\Users\Johnkallnaya\AppData\Local\Programs\Python\Python314\Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel\runw.exe
144302 INFO: checking EXE
144302 INFO: Building EXE because EXE-00.toc is non existent
144302 INFO: Building EXE from EXE-00.toc
144303 INFO: Copying bootloader EXE to C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\build\fts_terminal\BorsTerminal_Ultimate.exe
144318 INFO: Copying icon to EXE
144326 INFO: Copying 0 resources to EXE
144327 INFO: Embedding manifest in EXE
144335 INFO: Appending PKG archive to EXE
144375 INFO: Fixing EXE headers
145011 INFO: Building EXE from EXE-00.toc completed successfully.
145094 INFO: checking COLLECT
145094 INFO: Building COLLECT because COLLECT-00.toc is non existent
145095 INFO: Building COLLECT COLLECT-00.toc
149652 INFO: Building COLLECT COLLECT-00.toc completed successfully.
150050 INFO: Build complete! The results are available in: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist

=== frontend: npm run build ===
[OK] frontend: npm run build done in 23s

=== pyinstaller: fts_terminal.spec ===
[OK] pyinstaller: fts_terminal.spec done in 152s

=== DONE ===
output: C:\Users\Johnkallnaya\Desktop\Borsterminal\.worktrees\system2-perf\dist\BorsTerminal_Ultimate
size: 119.4 MB
BUILD_EXIT=0
```
