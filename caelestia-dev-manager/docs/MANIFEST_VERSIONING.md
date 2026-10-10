# Manifest versioning

`backend.schemas` is the central schema/migration registry. The existing spelling
`schema_version` is retained. Omission means schema 1. Both 1 and 2 are readable;
1 → 2 adds an explicit version deterministically, using copied data. Migration
never executes component code, writes source or installs anything. Unsupported
future versions fail with a readable schema_version error. Strict unknown/duplicate
fields remain errors, including nested declarations. `decode()` returns the
original text/object, source version, migration steps and normalized manifest;
`manifest_parse()` remains the compatible public normalized parser. Installed
source keeps its original manifest bytes and fingerprints.

Schema 2 adds optional `resources` (path → sha256/MIME descriptor) and
`portable_data` (root/path declarations restricted to children of
`caelestia-components/<id>` in XDG data/config/state). These declarations grant no
arbitrary destination or script execution. Python compatibility uses
`compatibility.python`, a packaging version specifier. See COMPONENT_SPEC for
transport and preparation behavior. Portable data declaration does not itself
export or mutate personal data; reviewed data transactions are a separate API.
