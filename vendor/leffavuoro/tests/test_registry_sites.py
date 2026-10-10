"""The registry and the adapters have to agree on provider ids.

`run.py` writes `data/venues-{provider}.json` from the `provider` string on a SITES entry;
the client looks that id up in `data/providers.json`, generated from the registry. Nothing
joins the two at runtime: a provider on one side only still fetches and renders, with no
label, host credit, booking verb or accent. The 2026-08-30 sweep took the eTiketti adapter
to sixteen sites, so the join is asserted here. The other direction too: a registry entry
whose module does not serve it is a chain in the picker that no fetch fills.
"""
import importlib
import unittest
from urllib.parse import urlsplit

import _ctx                                                # noqa: F401
import registry


def sites_by_module():
    """-> {module name: {provider id, ...}} for every module the registry names."""
    out = {}
    for name in registry.modules():
        mod = importlib.import_module(name)
        out[name] = {s["provider"] for s in mod.SITES}
    return out


class RegistrySitesTest(unittest.TestCase):
    def test_every_site_provider_has_a_registry_entry(self):
        for name, providers in sites_by_module().items():
            for pid in sorted(providers):
                with self.subTest(module=name, provider=pid):
                    self.assertIsNotNone(
                        registry.by_id(pid),
                        f"{name}.SITES has provider {pid!r} with no registry entry, "
                        f"so its venues would render with no chain label or accent")

    def test_every_registry_provider_is_served_by_its_module(self):
        by_module = sites_by_module()
        for p in registry.PROVIDERS:
            if not p["module"]:
                continue                    # Finnkino: own fetcher, no SITES
            with self.subTest(provider=p["id"]):
                self.assertIn(
                    p["id"], by_module.get(p["module"], set()),
                    f"registry says {p['id']!r} is served by {p['module']}.py, which "
                    f"has no SITES entry for it, so the chain would never be fetched")

    def test_a_sites_entry_declares_the_module_the_registry_names(self):
        """A provider moved to another adapter without its registry entry following
        would pass both checks above if the id merely exists somewhere."""
        by_module = sites_by_module()
        for name, providers in by_module.items():
            for pid in sorted(providers):
                entry = registry.by_id(pid)
                if entry is None:
                    continue                # reported by the first test
                with self.subTest(provider=pid):
                    self.assertEqual(
                        entry["module"], name,
                        f"{pid!r} is a SITES entry in {name}.py but the registry sends "
                        f"it to {entry['module']}.py")

    def test_venue_ids_are_unique_across_every_adapter(self):
        """A venue id is the area file's name (`data/area-{id}.json`), so a collision
        between two adapters is one cinema silently overwriting another's schedule."""
        seen = {}
        for name in registry.modules():
            mod = importlib.import_module(name)
            for site in mod.SITES:
                for v in site["venues"]:
                    with self.subTest(venue=v["id"]):
                        self.assertNotIn(
                            v["id"], seen,
                            f"venue id {v['id']!r} is used by {site['provider']} in "
                            f"{name}.py and already by {seen.get(v['id'])}")
                    seen[v["id"]] = f"{site['provider']} in {name}.py"

    def test_no_venue_id_is_all_digits(self):
        """Finnkino's theatre ids are numeric, and enrich_tmdb.py leaves every
        `area-<digits>.json` to fetch_data.py's own pass. A SITES venue with such an id
        would get no TMDB pass and no unpublish, silently."""
        for name in registry.modules():
            for site in importlib.import_module(name).SITES:
                for v in site["venues"]:
                    with self.subTest(venue=v["id"]):
                        self.assertFalse(v["id"].isdigit(),
                                         f"{v['id']!r} in {name}.py reads as a Finnkino id")

    def test_every_site_names_the_host_it_is_read_from(self):
        """`base` is the runner's pacing key: `run.py` serialises the sites sharing one
        and `run_cloud.py` groups them across modules, so a site declaring none joins one
        conservative group with every other base-less site in its half. CLAUDE.md states
        the rule, and it was prose alone until 2026-09-19, when a sweep of the hosts the
        committed logs name found Kino Engel and Kino Akseli declaring none. Both are
        local-half, where that shared group does not apply, which is why nothing failed
        and why nothing would have said so."""
        for name in registry.modules():
            mod = importlib.import_module(name)
            for site in mod.SITES:
                with self.subTest(module=name, provider=site.get("provider")):
                    host = urlsplit((site.get("base") or "").strip()).netloc
                    self.assertTrue(
                        host,
                        f"{name}.py's site {site.get('provider')!r} declares no usable "
                        f"`base`, so the runner cannot pace the host it reads")

    def test_a_site_link_is_only_a_cleartext_base_the_adapter_reads(self):
        """`site` replaces the `https://{host}/` link only for a host with no TLS (read
        2026-10-04: biosavoy.ax refuses 443, moviecompanyalatalo.fi has no address
        record). It must be the `http://` origin the provider's own adapter reads, which
        CLAUDE.md allows only with a recorded probe; anything else would be a second,
        unchecked way to send a reader to plain http."""
        found = {p["id"]: p["site"] for p in registry.PROVIDERS if p.get("site")}
        self.assertEqual(sorted(found), ["alatalo", "biosavoy"])
        for pid, site in found.items():
            with self.subTest(provider=pid):
                mod = importlib.import_module(registry.by_id(pid)["module"])
                bases = {urlsplit(s["base"]) for s in mod.SITES if s["provider"] == pid}
                url = urlsplit(site)
                self.assertEqual((url.scheme, url.path), ("http", "/"), site)
                self.assertIn((url.scheme, url.netloc), {(b.scheme, b.netloc) for b in bases})
        frontend = {p["id"]: p for p in registry.frontend()}
        self.assertEqual({k: v.get("site") for k, v in frontend.items() if "site" in v}, found)


if __name__ == "__main__":
    unittest.main()
