# HUST D3 pre-model runtime dependency addendum 002

- Date: 2026-08-19 (Asia/Shanghai)
- Status: frozen before the first HUST model fit or prediction
- Execution seal SHA-256: `ea64a99c20780ed4b2ffbe8d5c4b09ba4871ecbaa5911c43e7eca5b4fb20c9da`
- Scope: explicit transitive-code inventory only; no executable code or scientific rule changed

The metadata-only manifest locked all HUST-specific source files and the recorded-run repository
fingerprint, but its explicit source list did not enumerate every inherited SmartValve training
dependency. Before model execution, the following additional runtime files are therefore frozen.
The one-shot run must observe these exact SHA-256 values:

| Runtime dependency | SHA-256 |
|---|---|
| `scripts/paderborn_neural_protocol_contrast.py` | `d87f4d00327fc8ce98e504a2419893ea411dae5b4bb105a816b5dbf637ed00f6` |
| `src/smartvalve/config.py` | `e07d42f515e264370076266aa12a38cbfdcc086a40f0ee1abdac1d6ee2fdc0c2` |
| `src/smartvalve/experiments/cranfield_causal_audit.py` | `8b48c20e0b01eca98cc4a131eba7628a55eb21092c3e835db992473519010733` |
| `src/smartvalve/experiments/dg_expected_manifest.py` | `132882dd8e679b5720f0284b45039a7f26101a78ebed5eeb2d78dee08f9ee364` |
| `src/smartvalve/experiments/dg_training.py` | `da62cc1d177984573b61962daf482fc1d090892929ea775546b0e626b959df28` |
| `src/smartvalve/experiments/dg_losses.py` | `a84d4907b298a63db4c85b4669cfd7257b62b528fa824f84609910051f1ff85a` |
| `src/smartvalve/experiments/domain_data.py` | `3247e7ab7fc1ee64e43ffa7d9e897db022e98773991ab5a3ba050e2d5d65611a` |
| `src/smartvalve/experiments/paderborn_evaluation.py` | `54b32c96e1e908576ee08baa7850748fd4429ede2b9dd3195a022d6d2744831e` |
| `src/smartvalve/experiments/paderborn_protocol_contrast.py` | `ab0868435584a8cda8676f7fae87642151132f70277598a85c1dbdb4c72f88d9` |
| `src/smartvalve/experiments/pirl_sore.py` | `5eafbb9411763694e1412cce599aa5e30970b00db35b8d05c048a143468c06bc` |
| `src/smartvalve/experiments/dg_selection.py` | `2c7b296f19263e8abccbfd9a7b48a6fbc5117a8ddd0e7b9ffbd45279b78acb39` |
| `src/smartvalve/experiments/pirl_ratio_selection.py` | `87640dcd049b35c7341dc89397bad6a3d829e4079934e616a5743c84f8e4c0f8` |
| `src/smartvalve/experiments/pirl_development.py` | `314eb6d45372718c5ba9313da0b94655c2cf2ffe4688a9086ae4bd02f94fc01a` |
| `src/smartvalve/experiments/paderborn_domain.py` | `41e070c236a5000f63fc6bafb2a765dd00d53a51a0a5722fba8673ebf3b46aee` |
| `src/smartvalve/experiments/paderborn_structure_probe.py` | `0a7ae25c0d6faa72b66ec234a4671164172772b8428c083476466a67fba4b857` |

The feature artifact itself is already content-addressed by the execution seal, so dependencies
used only during completed feature extraction cannot alter the model input. This addendum closes
the explicit inventory gap for code used during configuration loading, fitting, and prediction.
