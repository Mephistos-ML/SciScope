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
