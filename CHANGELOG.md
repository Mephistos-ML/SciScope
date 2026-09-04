## [1.14.1](https://github.com/Mephistos-ML/SciScope/compare/v1.14.0...v1.14.1) (2026-09-04)


### Bug Fixes

* **search:** fail semantic backfills on embedding errors ([07233eb](https://github.com/Mephistos-ML/SciScope/commit/07233ebd4af440001a7df82ae82753e171aeb243))

# [1.14.0](https://github.com/Mephistos-ML/SciScope/compare/v1.13.1...v1.14.0) (2026-09-03)


### Features

* **search:** add hybrid semantic catalog retrieval ([388737b](https://github.com/Mephistos-ML/SciScope/commit/388737bd262aa30c3eefc91429c474e100f05046))
* **storage:** add semantic catalog indexes ([eba5a20](https://github.com/Mephistos-ML/SciScope/commit/eba5a208d40beb0cefc60845f8ba6bf4e74e953c))

## [1.13.1](https://github.com/Mephistos-ML/SciScope/compare/v1.13.0...v1.13.1) (2026-09-03)


### Bug Fixes

* **ranking:** normalize catalog query evidence ([ba39f5b](https://github.com/Mephistos-ML/SciScope/commit/ba39f5b3ba012f76d1883b46ffb4e7ca23108d2d))

# [1.13.0](https://github.com/Mephistos-ML/SciScope/compare/v1.12.1...v1.13.0) (2026-09-03)


### Bug Fixes

* **catalog:** standardize canonical repository profiles ([932505b](https://github.com/Mephistos-ML/SciScope/commit/932505b5b0fc29b92be1a3d0ca0d15812f8c25b6))


### Features

* **explore:** add result controls and beta dataset capture ([fa4b96a](https://github.com/Mephistos-ML/SciScope/commit/fa4b96a3a371913a153c6e2883e6529a376afa4d))

## [1.12.1](https://github.com/Mephistos-ML/SciScope/compare/v1.12.0...v1.12.1) (2026-09-02)


### Bug Fixes

* **search:** avoid JSON distinct in catalog retrieval ([e197658](https://github.com/Mephistos-ML/SciScope/commit/e197658817b0bf0a5fd33a264c26c7985c630eff))

# [1.12.0](https://github.com/Mephistos-ML/SciScope/compare/v1.11.2...v1.12.0) (2026-09-02)


### Features

* **catalog:** add persistent repository catalog ([1a4df28](https://github.com/Mephistos-ML/SciScope/commit/1a4df283605a3325f4ad6cbd85ea2b6f1bf41d4b))
* **search:** use local repository catalog before providers ([dfe18ed](https://github.com/Mephistos-ML/SciScope/commit/dfe18ed9cccba06000aa4e0c16be693fe03b4250))
* **sources:** expose stable provider repository ids ([2dd66ea](https://github.com/Mephistos-ML/SciScope/commit/2dd66ea402810db08e6d931e5ebf7ab01fd4cd99))

## [1.11.2](https://github.com/Mephistos-ML/SciScope/compare/v1.11.1...v1.11.2) (2026-09-02)


### Bug Fixes

* **search:** stop code retrieval after rate limits ([3e3244a](https://github.com/Mephistos-ML/SciScope/commit/3e3244acb5746cbc7fc6733355f3f9a0f1ac60d5))

## [1.11.1](https://github.com/Mephistos-ML/SciScope/compare/v1.11.0...v1.11.1) (2026-09-02)


### Bug Fixes

* **search:** reject conference repositories by name ([24108e7](https://github.com/Mephistos-ML/SciScope/commit/24108e76de22e20865d254092d65ec6d08c0e16e))

# [1.11.0](https://github.com/Mephistos-ML/SciScope/compare/v1.10.1...v1.11.0) (2026-09-02)


### Bug Fixes

* **search:** retain code hits after query timeout ([e7a8877](https://github.com/Mephistos-ML/SciScope/commit/e7a8877c2578824a19b9e4f68c427b30a1a4f3f9))
* **web:** clamp repository descriptions ([bbd628e](https://github.com/Mephistos-ML/SciScope/commit/bbd628e17f674b8c9a0fd4930fb4fe3e7f389138))


### Features

* **access:** bypass search quotas for internal users ([141790b](https://github.com/Mephistos-ML/SciScope/commit/141790b25ebb6305f05a671a6a282db3051078bd))

## [1.10.1](https://github.com/Mephistos-ML/SciScope/compare/v1.10.0...v1.10.1) (2026-09-01)


### Bug Fixes

* **search:** tighten repository admission and ranking cutoff ([8e380f5](https://github.com/Mephistos-ML/SciScope/commit/8e380f5cefa8fcf0719d74abad0769c8286f8777))

# [1.10.0](https://github.com/Mephistos-ML/SciScope/compare/v1.9.0...v1.10.0) (2026-09-01)


### Bug Fixes

* **search:** deduplicate ranking evidence density ([4747345](https://github.com/Mephistos-ML/SciScope/commit/47473457724c232cb687eb9c58267c50ef517746))


### Features

* **search:** add internal beta diagnostics mode ([41fc447](https://github.com/Mephistos-ML/SciScope/commit/41fc44794a3fec651cefa3d69ffa7af54abf8d77))
* **search:** add source-agnostic heuristic ranking ([879446d](https://github.com/Mephistos-ML/SciScope/commit/879446dff4592aa5b997063dcc3d50aae5a8df70))
* **search:** apply heuristic ranking to explore results ([0337dc3](https://github.com/Mephistos-ML/SciScope/commit/0337dc36dd02144558639465579cdd00a349f037))
* **search:** rank repository matches by evidence location ([97247ca](https://github.com/Mephistos-ML/SciScope/commit/97247caedb646c161bcc15c1cff89218aee4393b))
* **web:** add explore beta diagnostics toggle ([8891fd1](https://github.com/Mephistos-ML/SciScope/commit/8891fd117b24c737c5e6e4b5bd29f1130cefd6e1))

# [1.9.0](https://github.com/Mephistos-ML/SciScope/compare/v1.8.2...v1.9.0) (2026-08-27)


### Features

* **feed:** replace signal delivery with durable user feed events ([5532268](https://github.com/Mephistos-ML/SciScope/commit/553226848dc1b6d691ab6dd685ebc56baeaaa1b7))
* **monitoring:** track release and default-branch commit activity ([6d6f36e](https://github.com/Mephistos-ML/SciScope/commit/6d6f36e47977f4c4887b19073e25d6e4c62a1db6))
* **web:** split feed and subscription management views ([15abf41](https://github.com/Mephistos-ML/SciScope/commit/15abf41aebcf7613619e93d4b9902882c333c989))

## [1.8.2](https://github.com/Mephistos-ML/SciScope/compare/v1.8.1...v1.8.2) (2026-08-27)


### Bug Fixes

* **search:** reject thesis-style repository names ([2dddcc8](https://github.com/Mephistos-ML/SciScope/commit/2dddcc8318aa40f4ac3cbaed924a86c3122e066f))
* **web:** remove matched-term chips from explore results ([519b507](https://github.com/Mephistos-ML/SciScope/commit/519b5078302377505f252b48a19d904e98a9ce81))

## [1.8.1](https://github.com/Mephistos-ML/SciScope/compare/v1.8.0...v1.8.1) (2026-08-27)


### Bug Fixes

* **search:** tighten planner query generation rules ([cc1b635](https://github.com/Mephistos-ML/SciScope/commit/cc1b6357b7d87c975847dd400e7b54a13c971ae8))

# [1.8.0](https://github.com/Mephistos-ML/SciScope/compare/v1.7.2...v1.8.0) (2026-08-27)


### Features

* **search:** paginate GitHub code search candidates ([201574b](https://github.com/Mephistos-ML/SciScope/commit/201574bd6011f3653f44d20e168c53b483a8ac03))
* **search:** parallelize and split retrieval orchestration ([07fd210](https://github.com/Mephistos-ML/SciScope/commit/07fd210fe30ab20abc39ec6f0a947959fc6a76e1))
* **search:** parallelize external retrieval lanes ([3ae31a0](https://github.com/Mephistos-ML/SciScope/commit/3ae31a0cfe1d319aa569bcfdcca0c76b9388e32a))
* **search:** tighten AI query planning for explore ([1305d2a](https://github.com/Mephistos-ML/SciScope/commit/1305d2aee685545fdf6a73cbe76084c6a35173de))
* **web:** show high-level explore search stages ([a10b797](https://github.com/Mephistos-ML/SciScope/commit/a10b797dac8f6ed4d803e6eeb469588806a4c078)), closes [hi#level](https://github.com/hi/issues/level)

## [1.7.2](https://github.com/Mephistos-ML/SciScope/compare/v1.7.1...v1.7.2) (2026-08-27)


### Bug Fixes

* **infra:** attach app logger handler for search events ([97cd0ef](https://github.com/Mephistos-ML/SciScope/commit/97cd0ef4a7d2584a0ae4cad7306d46506424c0ea))

## [1.7.1](https://github.com/Mephistos-ML/SciScope/compare/v1.7.0...v1.7.1) (2026-08-27)


### Bug Fixes

* **infra:** configure app log level at startup ([c0dc043](https://github.com/Mephistos-ML/SciScope/commit/c0dc0436ec679eb530da4122215ccecb7b1e7a48))

# [1.7.0](https://github.com/Mephistos-ML/SciScope/compare/v1.6.4...v1.7.0) (2026-08-27)


### Features

* **search:** add admission decision buckets ([6c87e03](https://github.com/Mephistos-ML/SciScope/commit/6c87e0334adab842047934ea168d2f0e3e338446))
* **search:** add structured observability events ([ec7a842](https://github.com/Mephistos-ML/SciScope/commit/ec7a8424ea3587541090b657fd13b7f028126020))
* **search:** enrich explore completion timing logs ([da8f34a](https://github.com/Mephistos-ML/SciScope/commit/da8f34af9638001981a3b2ce29d584bc38dcb42a))

## [1.6.4](https://github.com/Mephistos-ML/SciScope/compare/v1.6.3...v1.6.4) (2026-08-26)


### Bug Fixes

* **web:** improve mobile layout for explore results ([010f640](https://github.com/Mephistos-ML/SciScope/commit/010f640c857efd8f5f941854e2191aef38d1d4a4))

## [1.6.3](https://github.com/Mephistos-ML/SciScope/compare/v1.6.2...v1.6.3) (2026-08-26)


### Bug Fixes

* **ai:** tighten planner queries for scientific retrieval ([3d829d3](https://github.com/Mephistos-ML/SciScope/commit/3d829d344c9f26b1bbaec94b1423e221150cea11))
* **search:** preserve repository metadata when merging retrieval hits ([6416c5a](https://github.com/Mephistos-ML/SciScope/commit/6416c5a2d4d9c1e43d5c484a2692b76129c724b7))

## [1.6.2](https://github.com/Mephistos-ML/SciScope/compare/v1.6.1...v1.6.2) (2026-08-26)


### Bug Fixes

* **search:** reduce false rejects in admission filter and expand admission code signals for scientific repos ([8bf8f02](https://github.com/Mephistos-ML/SciScope/commit/8bf8f02db9ef8c196c045d46abe19ae74b494d26))

## [1.6.1](https://github.com/Mephistos-ML/SciScope/compare/v1.6.0...v1.6.1) (2026-08-26)


### Bug Fixes

* **search:** refine admission rules for scientific software recall ([016fb4f](https://github.com/Mephistos-ML/SciScope/commit/016fb4f3f616e3203cd86ebe3c691a26fe44b332))

# [1.6.0](https://github.com/Mephistos-ML/SciScope/compare/v1.5.1...v1.6.0) (2026-08-26)


### Features

* **search:** add shadow admission filter for explore results ([d399fa9](https://github.com/Mephistos-ML/SciScope/commit/d399fa98cb0e619e7ecefc20ee4620e0f7629d64))

## [1.5.1](https://github.com/Mephistos-ML/SciScope/compare/v1.5.0...v1.5.1) (2026-08-22)


### Bug Fixes

* **search:** classify source transport timeouts ([5e10687](https://github.com/Mephistos-ML/SciScope/commit/5e10687b7bc0993340c1ebfc0f780266ca7d8a07))

# [1.5.0](https://github.com/Mephistos-ML/SciScope/compare/v1.4.0...v1.5.0) (2026-08-22)


### Features

* **explore:** add async search jobs with polling ([5eeecb6](https://github.com/Mephistos-ML/SciScope/commit/5eeecb6e93b4c2d70a1ca757890c7d9cc2e89b65))
* **explore:** add time budgets and partial completion ([c17656e](https://github.com/Mephistos-ML/SciScope/commit/c17656e716759c73d10c09592e099079cda7bce2))

# [1.4.0](https://github.com/Mephistos-ML/SciScope/compare/v1.3.0...v1.4.0) (2026-08-22)


### Features

* **search:** replace readme retrieval lane with direct code search ([f380079](https://github.com/Mephistos-ML/SciScope/commit/f3800791599b981e2f92c466f30c4fd168b90978))

# [1.3.0](https://github.com/Mephistos-ML/SciScope/compare/v1.2.0...v1.3.0) (2026-08-22)


### Features

* **frontend:** paginate explore results and refine search loading state ([2a1c264](https://github.com/Mephistos-ML/SciScope/commit/2a1c264c9e8e21a8b5d1996a8482c2938f872075))

# [1.2.0](https://github.com/Mephistos-ML/SciScope/compare/v1.1.0...v1.2.0) (2026-08-21)


### Features

* **api:** add explore access and turnstile config ([fed0eee](https://github.com/Mephistos-ML/SciScope/commit/fed0eee37b1439f1fed64f542104bd9b7109db6a))
* **api:** add explore access models and errors ([1e9e5e8](https://github.com/Mephistos-ML/SciScope/commit/1e9e5e8b6e946f7d0bec113f205b1c08a891a839))
* **api:** add explore access policy and actor checks ([93f212c](https://github.com/Mephistos-ML/SciScope/commit/93f212c18725e884bd521f719f284c97ef0e4056))
* **api:** enforce explore abuse protection ([3107d07](https://github.com/Mephistos-ML/SciScope/commit/3107d076f57559f87dc9fdd21c31776dcb30bd6e))
* **api:** finalize explore abuse flow ([ae58d2d](https://github.com/Mephistos-ML/SciScope/commit/ae58d2d244f27f43a68255972e7a541a7c62fbfd))
* **db:** add explore usage event storage ([915816f](https://github.com/Mephistos-ML/SciScope/commit/915816fb033c3c68d27aaa05c76925ebfba57756))
* **frontend:** add explore abuse protection states ([a873bf4](https://github.com/Mephistos-ML/SciScope/commit/a873bf41a88b60c1be4687572716c0bec13eeda3))
* **frontend:** add glass-like shell styling ([ce4cad2](https://github.com/Mephistos-ML/SciScope/commit/ce4cad2941c2e210b3090b97611584c3e597697f))
* **frontend:** show repository subscription dates ([8055bf9](https://github.com/Mephistos-ML/SciScope/commit/8055bf9c7dd5f6562222c9d6d4e4491f6d25f392))

# [1.1.0](https://github.com/Mephistos-ML/SciScope/compare/v1.0.2...v1.1.0) (2026-08-20)


### Bug Fixes

* **frontend:** refine shell viewport and top bar spacing ([2877419](https://github.com/Mephistos-ML/SciScope/commit/28774196e4d776cc0151b6404f9514302c654688))


### Features

* **frontend:** add application shell ([f52705c](https://github.com/Mephistos-ML/SciScope/commit/f52705c5d85c3a23db454eb754b804053d2d344b))
* **frontend:** add design token foundation ([88e0ece](https://github.com/Mephistos-ML/SciScope/commit/88e0ece9364da12f1feb277258850efd2e0eaa52))
* **frontend:** add explore no-results state ([eb389e8](https://github.com/Mephistos-ML/SciScope/commit/eb389e89caf2602b995d285dcf4c09ff45fad9a4))
* **frontend:** add sciscope favicon ([f802770](https://github.com/Mephistos-ML/SciScope/commit/f8027700a923d9a76e959b6408b209c747fbead8))
* **frontend:** redesign explore pre-search state ([02e3f44](https://github.com/Mephistos-ML/SciScope/commit/02e3f4423023809a8b978f2f3c58bbecbb65639c))
* **frontend:** redesign explore results state ([c96c427](https://github.com/Mephistos-ML/SciScope/commit/c96c427b91a1d280a2f4dfc6c82846b5c57a0925))
* **frontend:** redesign feed empty states ([bb060eb](https://github.com/Mephistos-ML/SciScope/commit/bb060eba3b026f3495dfc0ee1815359f0eb972f9))
* **frontend:** redesign populated feed state ([0ad893a](https://github.com/Mephistos-ML/SciScope/commit/0ad893ad6383f5c61619720af3cd641f77dddbc9))
* **frontend:** refine app shell and explore onboarding ([5018e63](https://github.com/Mephistos-ML/SciScope/commit/5018e6378a257eec92ad24c38863fc1ae6243862))

## [1.0.2](https://github.com/Mephistos-ML/SciScope/compare/v1.0.1...v1.0.2) (2026-08-14)


### Bug Fixes

* **db:** remove duplicate alembic head ([0303809](https://github.com/Mephistos-ML/SciScope/commit/03038091e40c8c1c78a5e3e325120839901da0d6))

## [1.0.1](https://github.com/Mephistos-ML/SciScope/compare/v1.0.0...v1.0.1) (2026-08-14)


### Bug Fixes

* **db:** shorten alembic revision id ([f1368b4](https://github.com/Mephistos-ML/SciScope/commit/f1368b4f105813108afeb1d68a57cf662b3b7fed))

# 1.0.0 (2026-08-14)


### Bug Fixes

* **ai:** log openai error response bodies ([968e4f2](https://github.com/Mephistos-ML/SciScope/commit/968e4f278f8c2d3c6e731b4b63de43d58ce5d41a))
* **ai:** log planner failures in explore flow ([a7acd1c](https://github.com/Mephistos-ML/SciScope/commit/a7acd1c437dd932b7142dacb50d37b32e8a5f185))
* **ai:** parse structured text from openai responses api ([aa1445d](https://github.com/Mephistos-ML/SciScope/commit/aa1445daac08f08bdd2219a9a6d1fd62b4058194))
* **api:** isolate repository source failures in explore search ([bf8048a](https://github.com/Mephistos-ML/SciScope/commit/bf8048aada35d74cc6642232145e0e6a2558b576))
* **frontend:** increase api timeout for cold starts ([b8a02b5](https://github.com/Mephistos-ML/SciScope/commit/b8a02b5e5c4dbd7348d97f62b5e64392071c13cf))
* **infra:** make initial migration safe for legacy production schema ([ac3793d](https://github.com/Mephistos-ML/SciScope/commit/ac3793d9004dfaec61992103e63a9c0211bfb2ac))


### Features

* add dashboard debug visibility for live pipeline ([4577d7a](https://github.com/Mephistos-ML/SciScope/commit/4577d7a39f17b29d43307696ac1d01ee8a846c09))
* add github discovery pipeline and entity memory ([f092e95](https://github.com/Mephistos-ML/SciScope/commit/f092e951baf16a1d924b1b579a8e03b9a34efc75))
* add github token auth support ([9ffcaae](https://github.com/Mephistos-ML/SciScope/commit/9ffcaae9748d6791a28a744a09f6be2dde20099f))
* add gitlab repository monitoring ([eeb644a](https://github.com/Mephistos-ML/SciScope/commit/eeb644a28be5dd70da23a625de6bc62c2f3048ea))
* add source logos to github signal views ([532281e](https://github.com/Mephistos-ML/SciScope/commit/532281e8a377b1541ef845f2c91714108584d20d))
* **ai:** add bootstrap search plan foundation ([335a34d](https://github.com/Mephistos-ML/SciScope/commit/335a34dac25f9d5a6e79de19b8a6c8bffefba9fa))
* **ai:** add openai planner foundation ([c4c4359](https://github.com/Mephistos-ML/SciScope/commit/c4c43598c6c63cd1b457b2291dd739cee2f9d4d0))
* **ai:** broaden planner queries for repository retrieval ([ef2b845](https://github.com/Mephistos-ML/SciScope/commit/ef2b84599145a9cedcdde8677e5eb1205df7c54a))
* **api:** add dev auth and subscription management ([ac883d8](https://github.com/Mephistos-ML/SciScope/commit/ac883d8a2e1cf970b2245a1fc187333b28679f00))
* **api:** migrate backend runtime to fastapi and uvicorn ([56376f3](https://github.com/Mephistos-ML/SciScope/commit/56376f3fc8c1dfcb946e3fabe8de6393074dfd7d))
* **auth:** add google oauth backend flow ([f7c3180](https://github.com/Mephistos-ML/SciScope/commit/f7c31804bc587436ea6a0575b52fde900b3c8a9d))
* **auth:** add persistent user oauth and session schema ([fac0c27](https://github.com/Mephistos-ML/SciScope/commit/fac0c27dd7e7ee15922560bbfd070ef0782d2bcc))
* **auth:** replace in-memory auth with db-backed sessions ([aa99659](https://github.com/Mephistos-ML/SciScope/commit/aa996592457513b149516ff1d1b18b075e103b70))
* **db:** add postgres foundation with sqlalchemy and alembic ([a2d94f7](https://github.com/Mephistos-ML/SciScope/commit/a2d94f73d8fbe112c96109f816ec9d911cecea6d))
* **explore:** add explicit query overrides for repo search ([449710c](https://github.com/Mephistos-ML/SciScope/commit/449710cc70fd81168a3107d0074c055581888716))
* **frontend:** add explore and feed app shell ([ab928bf](https://github.com/Mephistos-ML/SciScope/commit/ab928bf62e69721cee9438ed3e558b158ee03c47))
* **frontend:** harden production runtime configuration ([0ed9f95](https://github.com/Mephistos-ML/SciScope/commit/0ed9f9536ccf328195a90b898fda79028a33c68b))
* **frontend:** link explore source badges to repositories ([054f681](https://github.com/Mephistos-ML/SciScope/commit/054f681d8ba7ea6599ed62542f1610b9e89ac68f))
* **frontend:** switch auth flow to google sign-in ([cbbfb0e](https://github.com/Mephistos-ML/SciScope/commit/cbbfb0e1de8bf77044769f705448ca0704862c1d))
* initialize sciscope replay dashboard foundation ([e67adfc](https://github.com/Mephistos-ML/SciScope/commit/e67adfc7e449713d2a651666f096da1fb7b5d128))
* persist per-entity github release checkpoints ([bb959bc](https://github.com/Mephistos-ML/SciScope/commit/bb959bcbda7f9a1e6145cf5e40b68e093b9cbb32))
* **repositories:** add placeholder adapters for gitee gitcode and gitverse ([7c41e60](https://github.com/Mephistos-ML/SciScope/commit/7c41e60c7bd444cf5b30eaae632609be115d9171))
* **runtime:** support explore search and multi-subscription processing ([b1ad4de](https://github.com/Mephistos-ML/SciScope/commit/b1ad4deab8e7a07d3da309100568d81fd0000b21))
* **sources:** add repository auth foundation ([443d722](https://github.com/Mephistos-ML/SciScope/commit/443d72246795de6ca1e02cb93e7e74964a867acf))
