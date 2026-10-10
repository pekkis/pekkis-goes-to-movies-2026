#!/usr/bin/env python3
"""Single source of truth for providers.

Everything provider-specific that is not parsing lives here. data/providers.json is
generated from this by scripts/build_providers.py, so the frontend carries no provider
list of its own: adding a provider is an entry here plus an adapter.

Fields:
  id      matches the `provider` field on every show and data/venues-{id}.json
  label   chain name, used in the venue picker, the chain legend and the footer
  host    the cinema's own domain, credited in the footer
  accent  3 px left border in combined views. Never the sole signal: those views print
          the venue name and the chain legend too. Two views list chains together, a
          combined city and a region row from REGIONS, and both are measured. The scale
          is 14.4 ΔE00 across normal vision and both deuteranope models. Combined-city
          pairs hold it without exception, the worst being 14.409 (Kino Engel/Korjaamo
          Kino in Helsinki). Region pairs do not all hold it: 20 of the 166 pairs are
          below, worst 6.348 (Bio Grand/Kino K13 in Pääkaupunkiseutu), and all 20 are
          established colours docs/research/accent-colour.md lists. Score on the weakest
          of the three models: Kino Engel and Cinema Sheryl are 19.2 apart to a
          deuteranope and 16.6 to everyone else. A new or changed accent clears 14.4 in
          every view it enters, and must not lower an existing regional minimum without
          the reason recorded in IDEAS.md. A city with no colour left is re-solved as a
          whole rather than excused; CLAUDE.md states that rule and Helsinki is the case
          it was written for. Measured 2026-09-21: 13 cities hold more than one chain
          (Helsinki ten, Vantaa four, Espoo and Jyväskylä three, Forssa, Hyvinkää,
          Kouvola, Kuopio, Lahti, Oulu, Tampere, Turku and Vaasa two) and 12 of the 14 regions do,
          giving 66 city pairs and 166 region pairs. Run
          `python3 scripts/accent_check.py` before changing one: it prints every
          shared-view pair in CIEDE2000 under two deuteranope models, and `--search {id}`
          ranks replacements on their weakest model. Do not quote a figure no script
          produced; the numbers that used to sit here were CIE76 mislabelled as ΔE.
  book    buy | reserve | door | list | admission -> footer call to action. "list" is
          for a provider with no per-show booking URL, so a showtime opens the programme
          page (Gilda). "admission" is for a venue whose screenings are included in a
          general admission ticket (Heureka): the showtime links to the ticket shop and
          the price compartment stays blank
  module  scripts/providers/{module}.py. One module can serve several providers
          (nexxo -> kinoset, etiketti -> kotkanleffat). None = Finnkino, which has
          its own fetcher at scripts/fetch_data.py and the legacy areas.json shape
  where   local | cloud. Finnkino, Kino Engel, Kino Akseli, Joutsan Kino, Savon
          Kinot, Kino Regina, Cine, Elokuvateatteri Star and Elokuvateatteri Huvimylly
          block or challenge datacenter IPs, so they can only be fetched from an ordinary
          connection. Cinema Sheryl, Haapamäen Elokuvat and Elävienkuvien teatteri run
          local until a committed run log shows a runner can read them. Everything else
          runs on Actions
"""

PROVIDERS = [
    dict(id="finnkino", label="Finnkino", host="finnkino.fi", accent="#E4551F",
         book="buy", module=None, where="local"),
    # Violet since 2026-09-21, not the blue it carried: Helsinki reached ten chains and
    # no palette clears 14.4 there with this one held at #1273D4. The joint solve moved
    # four accents and this is the only one outside Helsinki, 4.4 dE00 from its old
    # colour. Its eleven other city views and six region rows were all re-measured.
    dict(id="biorex", label="BioRex", host="biorex.fi", accent="#AC14FC",
         book="buy", module="biorex", where="cloud"),
    dict(id="kinoset", label="Kinoset", host="kinoset.fi", accent="#0E9B63",
         book="reserve", module="nexxo", where="cloud"),
    dict(id="kotkanleffat", label="Kotkan Leffat", host="kotkanleffat.fi",
         accent="#C42749", book="buy", module="etiketti", where="cloud"),
    # Teal, not the violet it launched with. Violet and BioRex's blue differ almost
    # entirely in the red-green channel a deuteranope does not have -- 3.9 dE00 apart,
    # in the one city where the two appear side by side. Riviera moved rather than
    # BioRex because both its venues are in Helsinki, so its accent only ever matters
    # there, while BioRex's blue is unconstrained in eleven other towns.
    dict(id="riviera", label="Riviera", host="rivieracinemas.fi", accent="#0C6464",
         book="buy", module="riviera", where="cloud"),
    # Moved 2026-09-21 in the ten-chain Helsinki solve, 18.5 dE00 from its old colour.
    dict(id="gilda", label="Gilda", host="gilda.fi", accent="#A48C78",
         book="buy", module="gilda", where="cloud"),
    # Moved off Vista on 2026-08-30: the /xml/ services 404 from every network and the
    # site now runs eTiketti. Accent, host and venue ids are unchanged on purpose -- the
    # ids key the saved home cinema and the /teatteri/ URLs.
    # Local since 2026-09-04: savonkinot.fi sits behind Cloudflare, which answers a
    # datacenter address 403 at the edge (CF-Ray present, no Retry-After) while the same
    # request from an ordinary connection gets 200. See "Savon Kinot moves to the local
    # half" in docs/archive/2026-09-providers.md.
    dict(id="savonkinot", label="Savon Kinot", host="savonkinot.fi", accent="#0C8FA8",
         book="buy", module="etiketti", where="local"),
    dict(id="orion", label="Cinema Orion", host="cinemaorion.fi", accent="#4E7A16",
         book="buy", module="orion", where="cloud"),
    # Moved 2026-09-21 in the ten-chain Helsinki solve, 12.8 dE00 from its old colour.
    dict(id="engel", label="Kino Engel", host="kinoengel.fi", accent="#C4749C",
         book="buy", module="engel", where="local"),
    # Not the BioRex chain above: an independent cinema in Kokkola that shares the
    # name, on biorex.org rather than biorex.fi. Same trap as Gilda's Bio Rex
    # Lasipalatsi, so the label spells the city out and the accent sits far from
    # BioRex blue instead of near it.
    dict(id="biorexkokkola", label="Bio Rex Kokkola", host="biorex.org", accent="#006655",
         book="buy", module="etiketti", where="cloud"),
    dict(id="kinoakseli", label="Kino Akseli", host="kinoakseli.fi", accent="#B8801A",
         book="door", module="kinoakseli", where="local"),

    # The eTiketti sweep of 2026-08-30. Fourteen hosts, sixteen venues, all against the
    # parser that already served Kotka and Kokkola. Only three of them land in a city
    # that already had a chain, and those three accents are the only ones the 3 px rule
    # constrains -- see the sweep entry in docs/archive/2026-09-providers.md. Every one
    # publishes a per-show booking link, so `buy`.
    dict(id="kinopirtti", label="Kinopirtti", host="kinopirtti.fi", accent="#8E44AD",
         book="buy", module="etiketti", where="cloud"),
    dict(id="leffabuumi", label="Leffabuumi", host="leffabuumi.fi", accent="#1F7A8C",
         book="buy", module="etiketti", where="cloud"),
    dict(id="studio123jarvenpaa", label="Studio 123 Järvenpää", host="studiot123.com",
         accent="#B0308F", book="buy", module="etiketti", where="cloud"),
    # Kouvola is the one town this sweep puts two of its own chains in, so these two
    # accents are measured against each other and against nothing else -- and because
    # *both* are free, the pair is taken at the maximum the L* band allows rather than
    # merely far enough apart: 73.5 dE00 deutan, against the 35.2 they launched with.
    # Blue against orange is where that maximum lives, so both sit near an accent used
    # in another city (Kino Aurora's indigo, Finnkino's orange). Neither chain appears
    # outside Kouvola and the accent renders only inside a combined city view, so the
    # two are never on screen together.
    dict(id="studio123kouvola", label="Studio 123 Kouvola", host="studio123.fi",
         accent="#2040F0", book="buy", module="etiketti", where="cloud"),
    dict(id="kino123", label="Kino 123", host="kino123.fi", accent="#E07000",
         book="buy", module="etiketti", where="cloud"),
    dict(id="ihmekompleksi", label="Ihme Kompleksi", host="ihmekompleksi.fi",
         accent="#7A5CD0", book="buy", module="etiketti", where="cloud"),
    dict(id="kinotar", label="Kinotar 123", host="jamsankinotar.fi", accent="#2E7D5B",
         book="buy", module="etiketti", where="cloud"),
    dict(id="kinojuha", label="Kino Juha", host="kinojuha.fi", accent="#A6431F",
         book="buy", module="etiketti", where="cloud"),
    # Vantaa already has Finnkino Flamingo, so this one is measured against Finnkino's
    # orange. Green is what it must not be: 13.6 dE00 under the harsher deutan model.
    dict(id="biogrand", label="Bio Grand", host="biogrand.fi", accent="#7B4FB5",
         book="buy", module="etiketti", where="cloud"),
    dict(id="biovuoksi", label="Bio Vuoksi", host="biovuoksi.fi", accent="#3E6FA8",
         book="buy", module="etiketti", where="cloud"),
    # Lahti already has Finnkino Kuvapalatsi. Same constraint, same measurement.
    dict(id="kinoiiris", label="Kino Iiris", host="kinoiiris.com", accent="#2F6FD0",
         book="buy", module="etiketti", where="cloud"),
    # The only eTiketti site on the local half: its host 403s a datacenter IP the way
    # Finnkino and Engel do. It shares the etiketti module with sixteen cloud sites,
    # which is what site-level routing in run.py exists for.
    dict(id="joutsankino", label="Joutsan Kino", host="kino.joutsa.fi", accent="#96702A",
         book="buy", module="etiketti", where="local"),
    dict(id="kkino", label="K-Kino", host="k-kino.fi", accent="#4C6B1F",
         book="buy", module="etiketti", where="cloud"),
    dict(id="biograni", label="Bio Grani", host="biograni.fi", accent="#B03A55",
         book="buy", module="etiketti", where="cloud"),
    # kiertue.cine.fi publishes Cine Keuda-Talo in Kerava and Cine Nikkilä in Sipoo.
    # Neither city has another provider, but both sit in Keski-Uusimaa, where four
    # more chains are listed in one row: worst case 21.4 dE00, L* 59.2.
    # Local since the first cloud run: Cloudflare answered the runner 403 at the edge
    # (CF-Ray present) while an ordinary connection got 200. Same shape as Savon Kinot.
    dict(id="cine", label="Cine", host="kiertue.cine.fi", accent="#BA7E8A",
         book="buy", module="etiketti", where="local"),
    # Oulu already has Finnkino Plaza, so this accent is constrained: 50.0 normal,
    # 73.7 Viénot, 65.1 Machado against Finnkino orange, at L* 46.1. Kino Tapiola's
    # #003CFC is pinned unique by tests/test_tapiola.py and Star's own red is
    # L* 36.4, under the legible band; docs/archive/2026-09-providers.md records both.
    # `host` is the public
    # domain for the footer credit, the adapter reads lippu.
    # Local since the first cloud run: lippu. answered the runner a Cloudflare 403 at
    # the edge while an ordinary connection got 200.
    dict(id="star", label="Elokuvateatteri Star", host="elokuvateatteristar.fi",
         accent="#2563EB", book="buy", module="etiketti", where="local"),

    # The Nexxo sweep of 2026-08-30. Six cinemas on five hosts, against the adapter that
    # already served Kinoset. Only Kino Aurora lands in a city that already had a chain.
    # `book="reserve"` throughout: Nexxo publishes no per-show booking URL, so a showtime
    # opens the programme page filtered to that location, the same as Kinoset.
    #
    # Jyväskylä already has Finnkino Fantasia. Orange was the intuitive pick for a cinema
    # called Aurora and measures 4.7 dE00 against Finnkino's: indigo instead, at 63.7.
    dict(id="kinoaurora", label="Kino Aurora", host="kinoaurora.fi", accent="#5B4FD0",
         book="reserve", module="nexxo", where="cloud"),
    # Both read from kinohirvi.fi, which serves two cinemas in two towns on locationids
    # 2 and 4. Bio Säde's own domain, biosade.fi, answers with an empty programme, so the
    # host credited here is the one read.
    dict(id="kinohirvi", label="Kino Hirvi", host="kinohirvi.fi", accent="#0F7B9C",
         book="reserve", module="nexxo", where="cloud"),
    dict(id="biosade", label="Bio Säde", host="kinohirvi.fi", accent="#8C3B7A",
         book="reserve", module="nexxo", where="cloud"),
    dict(id="kinomarilyn", label="Kino Marilyn", host="kinomarilyn.fi", accent="#1A6E4A",
         book="reserve", module="nexxo", where="cloud"),
    dict(id="kinoolympia", label="Kino Olympia", host="kino-olympia.fi", accent="#9C5518",
         book="reserve", module="nexxo", where="cloud"),
    dict(id="jarvelankino", label="Järvelän Kino", host="jarvelankino.fi", accent="#7A6A1E",
         book="reserve", module="nexxo", where="cloud"),
    # KSEK's touring cinema, read from kinoaurora.fi (one deployment with ksek.fi);
    # the host credited is the one read, as with Bio Säde. Accent measured
    # 2026-08-31 against Muurame, Petäjävesi and Jyväskylä: worst same-city deutan
    # pair 26.9 dE00 (vs Finnkino and Kino Aurora in Jyväskylä), L* 46.9.
    dict(id="kinometso", label="Kino Metso", host="kinoaurora.fi", accent="#227D63",
         book="reserve", module="nexxo", where="cloud"),
    # Cinema Niagara, Tampere (2026-09-02): the eTiketti host the sweep left behind,
    # because its screenings render in a second template that etiketti.py now reads.
    # Tampere becomes the sixth two-chain city, so the accent is measured against
    # Finnkino's orange: #6A4FBF is 47.0 / 68.1 / 60.6 dE00 (normal / Viénot / Machado),
    # greens failed the deutan columns at 17-19, and no other chain uses this hex. The
    # cinema sells per-show tickets on its own /salikartta page, so `buy`. `where` is
    # provisional until a cloud run has succeeded: cinemaniagara.fi answered an ordinary
    # connection with no challenge and no Cloudflare header, which is how the other
    # cloud eTiketti hosts look, and one field flips it if a runner is refused.
    dict(id="niagara", label="Cinema Niagara", host="cinemaniagara.fi", accent="#6A4FBF",
         book="buy", module="etiketti", where="cloud"),
    # Heurekan planetaario, Vantaa (2026-09-05). Screenings are included in the day
    # admission and there is no planetarium ticket, so `admission`. Vantaa already holds
    # Finnkino and Bio Grand: #0B8468 measures 26.5 / 26.0 dE00 (Viénot / Machado) from
    # Finnkino's orange and 30.3 / 27.9 from Bio Grand's violet, L* 49.0; Heureka's own
    # lime green scores 6.9 against the orange. `where` is provisional as Niagara's was:
    # 200 from an ordinary connection and from a non-residential fetcher, Cloudflare in
    # front, no challenge. The first cloud run decides.
    # Local since 2026-10-03: four routine cloud runs in a row, 2026-10-02 08:48Z to
    # 17:17Z, got Cloudflare's 429 on the first request, while an ordinary connection read
    # the same 199 showtimes. Evidence in docs/research/runner-challenges.md.
    dict(id="heureka", label="Heureka", host="heureka.fi", accent="#0B8468",
         book="admission", module="heureka", where="local"),
    # Korjaamo Kino, Helsinki (2026-09-05): the Vista module's first site since Savon
    # Kinot left it. korjaamokino.fi answers the public /xml/ services to anyone, a
    # non-residential fetcher included, so `cloud`. Per-show ticket links to
    # /websales/show/{id}, so `buy`. Helsinki has six chains already, so the accent is
    # the search's best: #C07E7E measures 19.7 / 18.5 / 17.7 dE00 (normal / Viénot /
    # Machado) from Finnkino's orange and 21.3 / 20.1 / 17.9 from Gilda's magenta, its
    # two nearest; the other four sit above 23. L* 59.6, the top of the search band:
    # every darker rose tried (L* 49 to 55) fell to 13.8 to 14.4 deutan against Gilda.
    # Helsinki's worst pair stays Finnkino/Cinema Orion at 14.4.
    # Moved 2026-09-21 in the ten-chain Helsinki solve, 22.7 dE00 from its old colour.
    dict(id="korjaamo", label="Korjaamo Kino", host="korjaamokino.fi", accent="#80709C",
         book="buy", module="vista", where="cloud"),
    # Kino Tapiola, Espoo (2026-09-05): its own WordPress theme renders the programme
    # server-side, Johku sells the tickets through client-side embeds, so a showtime
    # opens the film page and `buy` is the verb. `where` is provisional as Korjaamo's
    # was: 200 from an ordinary connection and from a non-residential fetcher, nginx in
    # front, no challenge header; the first cloud run decides. Espoo holds Finnkino
    # Sello and Omena and nothing else, so the accent is measured against one orange
    # and the search's best is taken, as Kouvola's pair was: #003CFC is 52.7 / 80.4 /
    # 71.6 dE00 (normal / Viénot / Machado) from Finnkino, L* 38.3, the same blue band
    # as Studio 123 Kouvola, which never shares a screen with it.
    dict(id="tapiola", label="Kino Tapiola", host="kinotapiola.fi", accent="#003CFC",
         book="buy", module="tapiola", where="cloud"),
    # Kino Regina, Helsinki (2026-09-05): KAVI's cinema at Oodi. The theme's own POST
    # endpoint renders the schedule, each row with its ticket link into kauppa.kavi.fi,
    # so `buy`. `cloud` was read from a runner before the adapter was written, and two
    # of the first day's three runs published; the third got SiteGround's reputation
    # challenge, the 202 shell that keeps Kino Engel local, and now fails the venue
    # instead of emptying it. A repeat in the logs moves this entry to `local`.
    # Helsinki has seven chains already, so the accent is the search's best:
    # #8A4854 measures 18.4 / 19.9 / 18.4 dE00 (normal / Viénot / Machado) from Gilda's
    # magenta, 47.8 / 18.4 / 16.3 from Riviera's teal and 50.7 / 16.9 / 16.3 from Cinema
    # Orion's green, its three nearest; the other four sit above 20. L* 39.0. An eighth
    # chain in one city leaves only muted tones this far from everything; the greens the
    # search ranked higher on deutan fell to 12.5 to 14.1 in normal vision. Helsinki's
    # worst pair stays Finnkino/Cinema Orion at 14.4.
    dict(id="regina", label="Kino Regina", host="kinoregina.fi", accent="#8A4854",
         book="buy", module="regina", where="local"),

    # The Cinemahouse batch of 2026-09-14: three cinemas running the WordPress
    # `cinema-reservations` plugin under a cinemahouse-child theme, one adapter for all
    # three. `book="reserve"` throughout: the link a showtime carries,
    # /varaa/?screening_id=N, is a seat-reservation page that asks for a name, an email
    # and a phone number and ends in "Vahvista varaus", with no payment step anywhere in
    # it, so the showtime reserves a seat rather than selling a ticket. `where="cloud"`:
    # all three answer LiteSpeed with no Cloudflare and no challenge, and the first cloud
    # run decides as it did for Niagara and Heureka.
    #
    # Kaarina, Salo and Laitila each hold one cinema and none of the three is in a
    # REGIONS area, so none of these accents is constrained today and
    # `accent_check.py --search` says so for each. They are measured against Finnkino
    # anyway, because Kaarina is about 10 km from Turku and Turku is Finnkino's, so a
    # later Turun seutu entry would put that pair in one row: 51.2 / 65.5 / 57.5 dE00
    # (normal / Vienot / Machado) at L* 59.7 for Piispanristi, 35.2 / 37.8 / 34.7 at
    # L* 60.0 for Lumo, 47.6 / 35.8 / 34.1 at L* 46.5 for Laitila, and the three are 18.2
    # dE00 or more apart from each other. Against the whole 42-accent set the nearest
    # neighbour is 8.1 to 9.3 dE00, which is near the ceiling the L* 38-60 band still
    # offers: see docs/research/accent-colour.md, and it binds nothing, because an
    # accent is only ever read
    # beside the chains that share its city or its region.
    dict(id="kinopiispanristi", label="Kino Piispanristi", host="kinopiispanristi.fi",
         accent="#0096EA", book="reserve", module="cinemahouse", where="cloud"),
    dict(id="kinolumo", label="Kino Lumo", host="kinolumo.fi", accent="#F64EAE",
         book="reserve", module="cinemahouse", where="cloud"),
    dict(id="laitilankino", label="Laitilan Kino", host="laitilankino.fi",
         accent="#3C7872", book="reserve", module="cinemahouse", where="cloud"),

    # Iso-Hannu, Rauma (2026-09-15). Its own PHP, on none of the platforms already read
    # here, so it is the one parser in this batch: scripts/providers/isohannu.py.
    # `book="buy"`: the per-screening link is the cinema's own ticket shop and the button
    # it sits on reads "Osta liput". `where="cloud"`: www.isohannu.fi answers Apache with
    # no Cloudflare and no challenge, so it starts on the cloud half like every other
    # provider that shows no evidence of the datacenter block.
    # Rauma is in no REGIONS area and holds no other chain, so this accent enters no
    # shared view and `accent_check.py --search isohannu` answers "unconstrained. Nothing
    # to search". Measured against the whole set anyway, with accent_check's own dE:
    # L* 58.4, inside the set's 38-60 band, and 9.2 dE00 from its nearest accent on the
    # weakest of the three models (Kino Akseli), 14.5 in normal vision from Korjaamo Kino.
    # 14.4 is not reachable globally here -- a sweep of the band against all 42 existing
    # accents tops out at 9.2 -- which is why the rule binds shared views rather than the
    # whole set. It introduces no new pair anywhere: the worst pairs the full run prints
    # are the established ones it already listed.
    dict(id="isohannu", label="Iso-Hannu", host="isohannu.fi", accent="#FF4466",
         book="buy", module="isohannu", where="cloud"),

    # TMB Cinema Oy, 2026-09-15: four cinemas, one operator, one adapter
    # (scripts/providers/tmb.py). Four providers rather than one, because each carries its
    # own public brand and its own host, and `host` is the source line a reader sees in
    # the footer: "TMB Cinema" would name none of them. They are four cinemas and not one
    # mirrored four times -- the booking id differs per site for the same film at the same
    # minute, and the screen counts differ -- and the adapter docstring holds that
    # evidence.
    # `book="reserve"`: the showtime links to the public film page, not to the `?varaa=`
    # seat-reservation action, which this repo does not call and therefore could never
    # check before publishing. `where="cloud"`: all four answer Apache with no Cloudflare
    # and no challenge.
    # Akaa, Valkeakoski, Pieksämäki and Heinola hold no other chain and none is in a
    # REGIONS area, so these four accents enter no shared view and `accent_check.py
    # --search` says there is nothing to search for each. Measured against the whole set
    # anyway with accent_check's own dE: each is at least 6.3 dE00 from all 43 existing
    # accents on the weakest of the three models, and at least 18.4 from the other three
    # here. With 43 accents already in the 38-60 L* band, 6.3 is near the best available
    # globally, which is why the 14.4 rule binds shared views rather than the whole set.
    dict(id="kinotoijala", label="Kino-Toijala", host="toijalan-kino.info",
         accent="#555588", book="reserve", module="tmb", where="cloud"),
    dict(id="kinosampo", label="Kino-Sampo", host="kinosampo.info", accent="#336633",
         book="reserve", module="tmb", where="cloud"),
    dict(id="kinomania", label="KinoMania", host="kino-mania.info", accent="#EE0055",
         book="reserve", module="tmb", where="cloud"),
    dict(id="kinoelo", label="Elokuvateatteri Elo", host="elokuvat-elo.info",
         accent="#AA77AA", book="reserve", module="tmb", where="cloud"),

    # Julia 1&2, Hyvinkää (2026-09-15). Not the defunct Turku "Julia" a sweep recorded
    # earlier from a cinema-history page; this is an operating cinema on its own
    # WordPress. `book="door"`: it sells at the door and takes reservations by phone, so
    # there is no ticket host to link to and none is invented.
    # Unlike the TMB four, this accent is constrained: Hyvinkää already holds BioRex, and
    # Keski-Uusimaa holds BioRex, Cine, Kino Juha and Studio 123 Järvenpää. Chosen with
    # `accent_check.py --search julia`; the figures are in IDEAS.md and the archive.
    dict(id="julia", label="Julia 1&2", host="juliaelokuvat.fi", accent="#12664E",
         book="door", module="julia", where="cloud"),

    # Bio-Kaari, Forssa (2026-09-15). A MyCloudCinema cinema, which is a lead and not an
    # adapter: BioRex, Gilda and this one all run on that platform and all three render it
    # differently, so it gets its own parser, scripts/providers/biokaari.py.
    # `book="buy"`: the showtime carries the cinema's own web-sales link, read from the
    # page rather than constructed, and upgraded to the https its host redirects to.
    # Forssa holds no other chain and is in no REGIONS area, so this accent enters no
    # shared view; measured against the whole set anyway at 6.2 dE00 from its nearest on
    # the weakest of three models, which is near the best available with 48 accents
    # already in the band.
    dict(id="biokaari", label="Bio-Kaari", host="bio-kaari.fi", accent="#DD1100",
         book="buy", module="biokaari", where="cloud"),

    # Kino Vaakuna, Lohja (2026-09-15). Its own site, its own parser. The first provider
    # here whose pages publish no year at all, so it is also the first user of
    # `common.resolve_year`; see that function for why "nearest occurrence" rather than
    # "next occurrence".
    # `book="reserve"`: "Varaa liput" opens the film's own page and the cinema takes
    # reservations by phone and email, so there is no purchase link and none is invented.
    # No auditorium is invented either; the page names none.
    # Lohja holds no other chain and is in no REGIONS area, so this accent enters no
    # shared view; measured at 6.1 dE00 from its nearest on the weakest of three models.
    dict(id="vaakuna", label="Kino Vaakuna", host="kinovaakuna.fi", accent="#CC4477",
         book="reserve", module="vaakuna", where="cloud"),

    # Kuvakukko, 2026-09-15: Kino Kuvakukko (Kuopio) and Nilsiän Kino Manttu, the city of
    # Kuopio's two cinemas, whose schedules share one page. One provider with two venues,
    # the shape Kino Metso and Savon Kinot already use for an operator whose venues share
    # a source.
    # `book="door"`: the page says "Lipunmyynti vain Kuvakukossa" and, for Manttu, "Ei
    # ennakkovarauksia ... Maksuvälineenä käy vain käteinen". No online sale exists.
    # Kuopio already holds Finnkino, so this accent is constrained and was chosen with
    # `accent_check.py --search kuvakukko`; Nilsiä holds no other chain.
    dict(id="kuvakukko", label="Kuvakukko", host="kuvakukko.fi", accent="#7A3FB8",
         book="door", module="kuvakukko", where="cloud"),

    # Kino Kirkkonummi (2026-09-15). Deferred earlier the same day as too fragile to
    # parse; that was a maintenance judgement and the page did not bear it out, so it is
    # implemented. `book="list"` is exactly this case: the site is a single page with no
    # per-film page and no booking host, so a showtime opens the programme page, which is
    # what that mode means. Kirkkonummi holds no other chain and is not in a REGIONS area,
    # so the accent enters no shared view.
    dict(id="kirkkonummi", label="Kino Kirkkonummi", host="kinokirkkonummi.fi",
         accent="#BB6688", book="list", module="kirkkonummi", where="cloud"),

    # Bio Savoy, Mariehamn (2026-09-15). Åland, which nothing here covered. The one source
    # in this batch that infers nothing: every row carries a full ISO instant with its
    # offset, so `common.resolve_year` is not used and must not be.
    # **http only.** Port 443 is refused on both biosavoy.ax and www.biosavoy.ax, so every
    # published URL is http. That is the verified destination rather than an oversight;
    # inventing https would hand the reader a link that cannot connect, and `safeUrl()`
    # accepts http. `book="door"`: bookings are by telephone only.
    # Mariehamn is keyed under its own and only official name; see the module docstring for
    # why the Finnish exonym would be the wrong key here.
    # `site`: the address its own site answers at, linked by the status page and the stale
    # notice; see FRONTEND_OPTIONAL.
    dict(id="biosavoy", label="Bio Savoy", host="biosavoy.ax", accent="#7766FF",
         book="door", module="biosavoy", where="cloud", site="http://www.biosavoy.ax/"),

    # Cine Mäntsälä, Mäntsälä (2026-09-15). Separate from the `cine` entry above, which
    # is kiertue.cine.fi in Kerava and Sipoo: this is its own MyCloudCinema deployment on
    # its own host, with its own operator named in its own footer, and it runs on Actions
    # while Cine is local. Same shape as BioRex against Bio Rex Kokkola, so the label
    # spells the town out rather than leaving two rows both reading "Cine".
    # Mäntsälä holds no other provider and sits in no REGIONS area, so this accent enters
    # neither shared view. `accent_check.py --search cinemantsala` says exactly that:
    # "shares no city or region with another chain, so its accent is unconstrained".
    # Chosen anyway on the one hypothetical worth insuring against, Keski-Uusimaa being
    # the area Mäntsälä would join if the areas were ever extended: of twelve candidates
    # measured against that set this had the largest worst pair, 27.2 normal / 13.4
    # Viénot / 13.2 Machado. Nothing reaches 14.4 there -- the area already holds twelve
    # sub-threshold pairs of its own -- so the bar CLAUDE.md sets is not reachable in a
    # view this colour does not currently enter, and no existing minimum moves.
    # `book="buy"`: the site sells per-show tickets and each showtime links to the
    # `#/book/{show_time_id}` anchor the programme itself emits.
    dict(id="cinemantsala", label="Cine Mäntsälä", host="mantsala.cine.fi",
         accent="#5B21B6", book="buy", module="cinemantsala", where="cloud"),

    # Kino Kilta (Turku) and Kino Laika (Karkkila), 2026-09-15. Both on Kinola, which is
    # also Cinema Orion's platform, but neither renders the `kinola-day` table `orion.py`
    # reads, so they are a separate module with a handler per template rather than two
    # SITES entries. Kino Konepaja is the third Kinola tenant here and is deliberately
    # absent: re-read 2026-09-15, its screening list still says "Ei tulevia tapahtumia."
    # `book="buy"`: both sell per-screening through their own /checkout/{uuid}, and a
    # sold-out row falls back to the film page it emits.
    # Kilta's accent is constrained by Finnkino in Turku and in Turun seutu; Laika's is
    # not, Karkkila holding no other provider and sitting in no REGIONS area.
    dict(id="kinokilta", label="Kino Kilta", host="kinokilta.fi", accent="#1D6F8B",
         book="buy", module="kinola", where="cloud"),
    dict(id="kinolaika", label="Kino Laika", host="kinolaika.fi", accent="#9A3412",
         book="buy", module="kinola", where="cloud"),
    # Vantaa's fourth chain and Pääkaupunkiseutu's thirteenth. Measured 2026-09-18 with
    # accent_check.py: the Vantaa view clears the floor at 14.6 dE00 (Bio Grand, 17.9 to
    # normal vision), and the region does not, at 10.1 (Kino Engel, 15.0 normal) and 10.8
    # (BioRex). Of the 19 colours in the L* band that clear 14.4 in Vantaa and reach 10.0
    # in the region, this one has the highest worst normal-vision pair. The regional
    # minimum is unchanged at 4.5 (Bio Grand/BioRex). Reason recorded in IDEAS.md.
    dict(id="kinomyyri", label="Kino Myyri", host="kinomyyri.fi", accent="#807CFC",
         book="buy", module="kinola", where="cloud"),
    # Four Johku storefronts, 2026-09-18. Each is alone in its town, and none of Lapua,
    # Vihti, Tammisaari and Oulainen appears in REGIONS at all, so no region row holds
    # them either. That second half is a gap in the table rather than geography, and one
    # of the four has a plausible entry: Nummela, which Keski-Uusimaa lists, is a locality
    # of Vihti, 10 km from Vihdin Kino. So Vihdin Kino's accent is chosen against that
    # region's six chains as though it were already in it: 14.9 dE00 on the weakest model
    # and 20.6 to normal vision, the binding pairs being BioRex and Studio 123 Järvenpää.
    # Whether Vihti belongs in Keski-Uusimaa is a separate question and is in IDEAS.md.
    # The other three are unconstrained today and their accents are not pre-fitted.
    # "Bio Marilyn" and not "Bio Marilyn Lapua": the label and the venue name have to
    # match or `build_pages.label_of` concatenates them, which made the page slug read
    # bio-marilyn-lapua-bio-marilyn-lapua. Kino Marilyn in Loviisa keeps its own first
    # word and its own city, so the two do not read as one chain.
    dict(id="biomarilyn", label="Bio Marilyn", host="biomarilyn.com",
         accent="#B03A6A", book="buy", module="johku", where="cloud"),
    dict(id="vihdinkino", label="Vihdin Kino", host="vihdinkino.fi", accent="#AC7CD4",
         book="buy", module="johku", where="cloud"),
    dict(id="bioforum", label="Bio Forum", host="bioforum.fi", accent="#8C5A00",
         book="buy", module="johku", where="cloud"),
    dict(id="kinokulma", label="Kinokulma", host="kinokulma.fi", accent="#5A4FCF",
         book="buy", module="johku", where="cloud"),
    # Two cinemas on The Events Calendar, 2026-09-18. "Ritz Vaasa" spells the town: Kino
    # Ritz is a Leffabuumi venue in Mikkeli and the two share a name and nothing else.
    #
    # Vaasa holds BioRex and no region row holds the city, so that pair is the whole
    # constraint: 29.1 dE00 on the weakest model, 38.6 to normal vision. Muhos shares its
    # city with nobody and sits in no region, so nothing binds Tähti Kino today; its
    # accent is fitted to the row a future Oulun seutu would create, against
    # Elokuvateatteri Star and Finnkino, at 18.4, and kept 17.8 from Ritz Vaasa's.
    dict(id="ritzvaasa", label="Ritz Vaasa", host="ritz.fi", accent="#DC689C",
         book="buy", module="tribe", where="cloud"),
    dict(id="tahtikino", label="Tähti Kino", host="muhos.fi", accent="#15803D",
         book="buy", module="tribe", where="cloud"),
    # Kino Hamina, 2026-09-18. `book="door"` because the page says so in its own words:
    # "Ei ennakkovarauksia. Lipunmyynti alkaa n. 30min ennen elokuvan alkamista!", so there
    # is no ticket host to link to and none is invented. Same as Julia 1&2.
    # Hamina holds no other chain and sits in no REGIONS area, so nothing constrains this
    # accent today. Chosen against the row a Kymenlaakso extension would create, since
    # Hamina's nearest cinema city is Kotka: 21.2 dE00 on the weakest model against Kotkan
    # Leffat, 30.5 against Kino 123, 33.9 against Studio 123 Kouvola, and 28.8 from
    # Finnkino's orange, of 36,536 colours in the L* band that clear the floor there.
    dict(id="kinohamina", label="Kino Hamina", host="hamina.fi", accent="#0C9C88",
         book="door", module="hamina", where="cloud"),
    # Kinotour, 2026-09-18. A touring operator, so its venues are towns and the set grows
    # by observation; the adapter names an undeclared town in the run log every run rather
    # than failing on it.
    # None of the three towns it publishes today holds another chain or sits in a region
    # row, so nothing binds this accent now. It is fitted to the towns its own /locations/
    # list shows it visits, which do: Turku (Kino Kilta, Finnkino), Karkkila (Kino Laika)
    # and Piispanristi (Kino Piispanristi). 16.8 dE00 on the weakest model against that
    # set, of the 18,854 colours in the band that clear the floor there. Picked over an
    # equally distant teal so that two cinemas added the same day do not read alike.
    dict(id="kinotour", label="Kinotour", host="kinotour.fi", accent="#B0507C",
         book="buy", module="kinotour", where="cloud"),
    # Elokuvateatteri Marita, 2026-09-19. `book="door"` because the site carries no
    # `liput`, `varaa`, `osta` or `lipunmyynti` anywhere, so there is no ticket host to
    # link to and none is invented; a showtime opens the film's own page.
    # Outokumpu holds no other chain and sits in no REGIONS area, so nothing binds this
    # accent today. Fitted to the row a North Karelia extension would create, where its
    # only neighbour is Savon Kinot in Joensuu and Kitee: 31.4 dE00 on the weakest model
    # against it. Chosen for global distinctness rather than local room, since 14.4 is
    # unreachable against 66 accents already in the band: 5.3 from its nearest anywhere,
    # KinoMania, and 31.8 to 46.6 from the three cinemas added beside it the same day.
    dict(id="marita", label="Elokuvateatteri Marita", host="elokuvateatterimarita.fi",
         accent="#849666", book="door", module="marita", where="cloud"),
    # Lieksan Kino, 2026-09-19. `book="door"` in the page's own words: "Liput ovat
    # ostettavissa Lieksan kulttuurikeskuksen aulasta noin 30 minuuttia ennen näytöksen
    # alkua." The advance ticket it sells by phone is a voucher, not an online sale.
    # Lieksa holds no other chain and sits in no REGIONS area. Same North Karelia frame as
    # Marita, so the two were measured together: 16.3 dE00 on the weakest model against
    # Savon Kinot, the only chain either would meet, and 46.6 from Marita, which is the
    # pair most likely to share a future row. 4.3 from its nearest accent anywhere,
    # Kuvakukko, which is as far as the band reaches with 66 accents in it.
    dict(id="lieksankino", label="Lieksan Kino", host="lieksanelokuvat.net",
         accent="#2A5A9C", book="door", module="lieksa", where="cloud"),
    # Navettakino, 2026-09-19. A cinema in a cowshed, weekends only and irregular, which
    # is why its adapter confirms an empty weekend instead of ageing the last one.
    # `book="door"`: "Lippukassa avataan 30 minuuttia ennen ensimmäistä näytöstä."
    # Konnevesi holds no other chain and sits in no REGIONS area. Fitted to the row a
    # Keski-Suomi extension would create, where its neighbours are Kino Hirvi, Kino Metso,
    # Kino Aurora and Finnkino: 16.4 dE00 on the weakest model against that set. A purer
    # magenta measured 18.9 there and was passed over for this one at saturation 0.60,
    # which costs 2.5 dE00 against the set and nothing against the floor.
    dict(id="navettakino", label="Navettakino", host="navettakino.fi",
         accent="#E45CC0", book="door", module="navetta", where="cloud"),
    # Pyhäsalmen VPK, 2026-09-19. A volunteer fire brigade's cinema, read through the My
    # Calendar plugin's public REST route. `book="door"`: tickets at the door, reservations
    # by telephone, and the plugin's own event pages carry permalinks this endpoint does
    # not give. The city is the municipality, Pyhäjärvi, where the postal town is
    # Pyhäsalmi, which the label carries.
    # Pyhäjärvi holds no other chain and sits in no REGIONS area. Fitted to the row a
    # Pohjois-Savo extension would create, against Kuvakukko, Savon Kinot and Finnkino:
    # 17.6 dE00 on the weakest model against that set, and 18.9 from Lieksan Kino, the
    # nearest of the three added beside it the same day.
    dict(id="pyhasalmenvpk", label="Pyhäsalmen VPK", host="pyhasalmenvpk.fi",
         accent="#725466", book="door", module="vpk", where="cloud"),
    # Bio Pallas, 2026-09-19. A 1923 funkis cinema in Karjaa, in the municipality of
    # Raasepori, on a Wix front page that is its whole programme. `book="door"` in the
    # site's own words: "Paikkavaraukset vain Facebook mesengerillä tai soittamalla
    # numeroon", and no film row carries a ticket URL of any kind.
    # Karjaa holds no other chain and sits in no REGIONS area, so nothing binds this
    # accent today. Fitted to the row a Länsi-Uusimaa extension would create, where its
    # neighbours would be Bio Forum in the same municipality, Kino Laika, Kino Olympia,
    # Kino Akseli, Vihdin Kino and Kino Vaakuna: 18.6 dE00 on the weakest model against
    # that set, 21.1 to normal vision. 4.7 from its nearest accent anywhere, Bio Säde and
    # Laitilan Kino, which is as far as the L* 38 to 60 band reaches with 69 accents in
    # it; the colours that score better inside the row sit on top of Kino Tapiola.
    dict(id="biopallas", label="Bio Pallas", host="biopallas.com",
         accent="#546C78", book="door", module="pallas", where="cloud"),
    # Elokuvateatteri Huvimylly, 2026-09-19. Raahe's cinema, in the Tapahtumatalo hall,
    # programmed onto one hand-typed WordPress page. `book="door"`: "Elokuvalippuja voi
    # varata ja ostaa suoraan Raahesalin lipunmyynnistä", and tickets at the door half an
    # hour before the first screening. The label is the name the site gives itself eight
    # times on its own front page; "Bio Huvimylly" is the nytleffaan.fi directory's name.
    # Local, on the 2026-09-18 evidence: a non-residential address was served 403 with
    # `Server: Apache` and no `CF-Ray` where an ordinary connection gets 200. The runner
    # itself has never tried, and routing local on a 403 needs no runner evidence.
    # Raahe holds no other chain and sits in no REGIONS area. Fitted to the row a
    # Pohjois-Pohjanmaa extension would create, against Elokuvateatteri Star and Finnkino
    # in Oulu, Bio Rex Kokkola and Pyhäsalmen VPK: 18.9 dE00 on the weakest model against
    # that set, 21.5 to normal vision. 4.8 from its nearest accent anywhere,
    # Elokuvateatteri Elo. A fully saturated magenta scored 19.5 in the row and 5.7
    # anywhere and was passed over at saturation 0.94, the same call Navettakino's entry
    # records making at 0.60; this one is 0.53. Measured against Bio Pallas above on the
    # same pass, the two being the day's only additions: 14.8 dE00 apart, which clears the
    # 14.4 floor although no view puts them side by side.
    dict(id="huvimylly", label="Elokuvateatteri Huvimylly", host="huvimylly.com",
         accent="#CC60A0", book="door", module="huvimylly", where="local"),
    # Movie Company Alatalo, 2026-09-19. A touring operator, five towns, and the same
    # person who types huvimylly.com: both pages carry the same contact address and Raahe
    # is a venue this operator programmes. `book="door"`: "Liput elokuviin vain10-€
    # (Käteismaksu)" and no booking URL anywhere on the site. `host` is the site's own
    # domain although it serves http only; 443 refused the connection on 2026-09-19.
    # Cloud: the 2026-09-18 sweep read this host from a non-residential address, and the
    # runner log settles it the way Bio Pallas's did.
    # None of the five towns holds another chain or sits in a REGIONS area, so the accent
    # enters no shared view today and was fitted to the rows an extension would create:
    # Pohjois-Pohjanmaa (Finnkino and Star in Oulu, Huvimylly in Raahe, Kinokulma in
    # Oulainen, Tähti Kino in Muhos, Pyhäsalmen VPK) 14.8 dE00 on the weakest model,
    # Ylä-Savo (Savon Kinot, Finnkino and Kuvakukko) 19.7, Keski-Pohjanmaa (Bio Rex
    # Kokkola) 21.6, Lappi (BioRex in Rovaniemi, Kinopirtti in Kemi) 34.6. The binding
    # pair is Tähti Kino at 14.8, and Huvimylly itself is 16.9 away. 4.1 from its nearest
    # accent anywhere, Korjaamo Kino: the band is crowded at 71 accents and the median
    # nearest-neighbour distance in the set is 2.8, with 45 of the 71 below 4.1. Nothing
    # in the band clears 14.4 in all four rows and reaches 5.0 anywhere.
    dict(id="alatalo", label="Movie Company Alatalo", host="moviecompanyalatalo.fi",
         accent="#6C9678", book="door", module="alatalo", where="cloud",
         site="http://www.moviecompanyalatalo.fi/"),
    # Cinema Sheryl, 2026-09-19. A student-run cinema on the Aalto campus in Otaniemi and
    # the fourth tenant on `kinola.py`; the plugin runs in English there, which is the only
    # thing its template reads differently. `book="buy"`: every screening links to its film
    # page, which carries the buy button, the same call Kino Myyri's `/checkout/{uuid}`
    # got. Local until a committed run log proves otherwise, per the instruction of the
    # day; the three other Kinola tenants are cloud and routing is per site.
    # Espoo already holds Finnkino and Kino Tapiola, so this enters that city view and the
    # Pääkaupunkiseutu row. Measured: 42.0 dE00 against Finnkino and 19.8 against Kino
    # Tapiola on the weakest of the three models, both clear of 14.4. Pääkaupunkiseutu is
    # the crowded row and 14.4 is not reachable in it for any colour -- its own minimum is
    # 4.479, Bio Grand against BioRex -- so the binding rule there is not lowering it: this
    # sits 8.19 from its nearest in that row, well above. 5.5 from its nearest accent
    # anywhere, Savon Kinot, which shares no view with Espoo. L* 51.3, saturation 0.51.
    dict(id="sheryl", label="Cinema Sheryl", host="sheryl.fi",
         accent="#9E60C2", book="buy", module="kinola", where="local"),
    # Haapamäen Elokuvat, 2026-09-19. The village cinema in Haapamäki, Keuruu, run by
    # volunteers for the HPP sports club, and the fifth Johku storefront. `book="buy"`:
    # every row links to its own product page in the storefront, as the other four do.
    # Local until a committed run log proves otherwise, per the instruction of the day.
    # Haapamäki holds no other chain and sits in no REGIONS area. Fitted to the row a
    # Keski-Suomi extension would create, against Finnkino and Kino Aurora in Jyväskylä,
    # Kino Metso, Kino Hirvi in Äänekoski and Kinotar in Jämsä: 18.4 dE00 on the weakest
    # of the three models. 4.9 from its nearest accent anywhere, Kino Piispanristi in
    # Kaarina, which shares no view with it. L* 60.0, saturation 0.73; the colours that
    # scored better in the row all sit above 0.95, which is the saturation Elokuvateatteri
    # Huvimylly's entry records passing over.
    # Moved to eTiketti 2026-09-29: the site now serves that platform's listing and the
    # Johku parser read no screening from it. Same venue id, same accent.
    dict(id="haapamaki", label="Haapamäen Elokuvat", host="haapamaenelokuvat.fi",
         accent="#E644FE", book="buy", module="etiketti", where="local"),
    # Forssan Elävienkuvien teatteri, 2026-09-19. Finland's oldest operating countryside
    # cinema, 1906, 77 seats, on its own Foxy CMS and on none of the platforms. `book="buy"`:
    # each row links to the cinema's own `lipunvaraus/` seat picker for that screening.
    # Local until a committed run log proves otherwise, per the instruction of the day.
    # Forssa already holds Bio-Kaari, so this enters that city view: 39.5 dE00 apart on
    # the weakest of the three models, far clear of the 14.4 floor. Forssa sits in no
    # REGIONS area, so that view is the only one it enters. 5.9 from its nearest accent
    # anywhere, Studio 123 Järvenpää, with Savon Kinot the nearest teal at 6.1 and sharing
    # no view with it. L* 53.4, saturation 0.68.
    dict(id="elavienkuvien", label="Elävienkuvien teatteri",
         host="elavienkuvienteatteri.fi", accent="#2E8C92", book="buy",
         module="elavienkuvien", where="local"),
    # Kino Hannikainen, Nurmes, 2026-09-20. A Johku storefront on its own domain, the
    # sixth. The cinema is in Nurmes-talo and the 250-seat hall is named after the
    # composer Pekka Juhani Hannikainen; `loc` is the hall the rows carry.
    # Nurmes holds no other chain and no REGIONS area holds Nurmes, so this accent enters
    # no shared view and the floor binds nothing here. 4.2 dE00 from its nearest accent
    # anywhere, Kino Piispanristi in Kaarina, which shares no view with it. L* 55.0,
    # saturation 0.92.
    dict(id="kinohannikainen", label="Kino Hannikainen", host="kinohannikainen.net",
         accent="#1188DD", book="buy", module="johku", where="cloud"),
    # Kino Virta, Kalajoki, 2026-09-20. The seventh Johku storefront and the only one
    # served from the platform's own domain: virtasali.fi is the municipal hall's
    # WordPress page and every one of its ticket buttons points at kinovirta.johku.com,
    # which is what a showtime links to and what this reads. The hall is Virta-sali in
    # Kauppa- ja kulttuurikeskus Merta; the cinema calls itself Kino Virta.
    # Kalajoki holds no other chain and no REGIONS area holds it, so the accent enters no
    # shared view. 4.1 dE00 from its nearest accent anywhere, Gilda, which shares no view
    # with it. L* 45.7, saturation 0.92.
    dict(id="kinovirta", label="Kino Virta", host="kinovirta.johku.com",
         accent="#CC1188", book="buy", module="johku", where="cloud"),
    # Elokuvateatteri Matin-Tupa, Ylistaro, 2026-09-20. Founded 1941, 201 seats, on none
    # of the platforms: its programme is a server-rendered Toolset view on its own
    # WordPress, so it gets its own parser. `book="door"`, because the box office opens 30
    # minutes before the first screening and reservations are taken by telephone and
    # email; the site sells nothing online.
    # The town is the one the cinema gives as its address. Ylistaro has belonged to
    # Seinäjoki since 2009, and filing it under Seinäjoki would put it in that city view
    # beside BioRex, where this accent measures 8.3 dE00 on the weakest model, below the
    # 14.4 floor. Nilsiä under Kuopio and Haapamäki under Keuruu are the same call already
    # made. Ylistaro holds no other chain and no REGIONS area holds it, so the accent
    # enters no shared view. 4.1 dE00 from its nearest accent anywhere, Bio Grani, which
    # shares no view with it. L* 51.3, saturation 0.50.
    dict(id="matintupa", label="Elokuvateatteri Matin-Tupa", host="matin-tupa.fi",
         accent="#448855", book="door", module="matintupa", where="cloud"),
    # Kino Kuusamotalo, Kuusamo, 2026-09-20. 520 seats in the Oulankasali hall of the
    # town's culture house, run by its own operator on its own site. kuusamotalo.fi is
    # the culture house and only links here; its programme block is a Flockler embed and
    # names no film. On none of the platforms, so its own parser, over the WordPress
    # posts route. `book="door"`: the site sells nothing online and the desk opens an
    # hour before the screening.
    # Kuusamo holds no other chain and no REGIONS area holds it, so the accent enters no
    # shared view. 4.6 dE00 from its nearest accent anywhere, KinoMania in Pieksämäki,
    # which shares no view with it. L* 58.6, saturation 0.60.
    dict(id="kuusamotalo", label="Kino Kuusamotalo", host="kinokuusamotalo.fi",
         accent="#AA8844", book="door", module="kuusamotalo", where="cloud"),
    # Added 2026-09-21. Kino Akustiikka is the screen of Ylivieska's culture house and
    # has no site of its own: the town's Localhub event calendar carries the dated
    # screenings and `ylivieska.fi` carries the cinema. Read through the calendar's own
    # public search, with no authentication and no cookie. `book="buy"`: every row links
    # to the town's ticket shop, which sells the seat.
    # Ylivieska holds no other chain and no REGIONS area holds it, so the accent enters
    # no shared view. 4.5 dE00 from its nearest accent anywhere, Kino Akseli in
    # Järvenpää, which shares no view with it. L* 54.3, saturation 0.79.
    dict(id="kinoakustiikka", label="Kino Akustiikka", host="ylivieska.fi",
         accent="#988020", book="buy", module="localhub", where="cloud"),
    # Added 2026-09-21. A Duda site whose front page is the programme, one blog card per
    # film. On none of the platforms, so its own parser. `book="door"`: the site sells
    # nothing online and names no ticket host, and its own text says to buy at the
    # theatre.
    # Harjavalta holds no other chain and no REGIONS area holds it, so the accent enters
    # no shared view. 4.4 dE00 from its nearest accent anywhere, Bio Rex Kokkola, which
    # shares no view with it. L* 42.9, saturation 0.57.
    # Local since 2026-09-26: three runner fetches in a row, 2026-09-25 15:27Z to
    # 23:19Z, failed resolving the host, while an ordinary connection fetched and parsed
    # the same six showtimes. Evidence in docs/research/runner-challenges.md.
    dict(id="kinohuovi", label="Kino-Huovi", host="kinohuovi.fi",
         accent="#307060", book="door", module="kinohuovi", where="local"),
    # Added 2026-09-21, the ninth and tenth chains in Helsinki. Adding them is what
    # forced the joint solve above: with the eight existing accents held, the best colour
    # in the L* band reached 12.12 against them, and moving four of the eight lifts the
    # whole city to 14.409. Both were parsed against live data before either was written.
    #
    # Kino K13 is the Finnish Film Foundation's own screen on Katajanokka. `book="list"`:
    # the screenings are free and there is no per-show booking URL, so a showtime opens
    # the programme section, the mode Gilda already uses.
    # 0.6 dE00 from Lieksan Kino, which shares no city and no region with it; 50 pairs in
    # this palette sit under 4.0 dE00 and none of them share a view.
    dict(id="k13", label="Kino K13", host="ses.fi", accent="#185C98",
         book="list", module="k13", where="cloud"),
    # Kino Helios is the Malmitalo hall's cinema strand, read from the culture house's own
    # event calendar service. `book="buy"`: every row carries a lippu.fi ticket link.
    # `Doc Helios` is a different strand of the same house and is filtered out by subtitle.
    dict(id="helios", label="Kino Helios", host="malmitalo.fi", accent="#FC24EC",
         book="buy", module="helios", where="cloud"),
]

FRONTEND_KEYS = ("id", "label", "host", "accent", "book")
# `site` is set only where a provider's own site does not answer at `https://{host}/`:
# a host with no TLS, whose adapter `base` is the documented cleartext exception in
# CLAUDE.md (docs/research/adapter-http.md). Read 2026-10-04, biosavoy.ax refuses 443 and
# moviecompanyalatalo.fi has no address record, so both links built from `host` failed.
# `tests/test_registry_sites.py` holds every `site` to its adapter's `http://` base.
FRONTEND_OPTIONAL = ("site",)

# Areas the picker offers beside the cities, generated into data/regions.json by
# scripts/build_regions.py. Kept here rather than in index.html because that is the one
# file a provider change never touches: a cinema in a new town would otherwise land
# outside every area with nothing to catch it, and tests/test_regions.py fails on a city
# named here that has no venue.
#
# The rule: two or more cinema cities, and every pair inside the area close enough that
# a cinema in one town can replace one in another. Cities excluded on distance stay
# ordinary city rows, among them Sastamala against Kangasala, Jamsa against Aanekoski,
# Loimaa against Turku, Kuopio against Varkaus, Savonlinna against Mikkeli, Kitee against
# Joensuu, Vaasa against Kokkola and Rovaniemi against Kemi.
#
# **There is no distance field.** Each row carried a `km`, described as the longest hop
# inside the area and as an estimate. It was deleted on 2026-09-18 after one of the
# figures was measured and fitted neither of the two metrics the others fit: nothing
# read it, `regions()` never published it, and a number nobody consumes and nobody
# measures is a claim waiting to go stale. A radius, if one is ever needed, gets measured
# once on one stated metric with the source recorded. The record is in
# docs/archive/2026-09-providers.md.
#
# A city belongs to at most one area, so the areas never overlap and no cinema is
# reachable through two of them. Names are nominative and never inflected.
#
# `name` is the Finnish name and the key: data/regions.json, the `region:` preference and
# the ?area= links are all keyed by it, so translating it would break every stored value
# and every deep link, exactly as CITY_SV in index.html is display-only. `sv` and `en` are
# the display names, and the picker's search matches all three in every language, the way
# a Turku venue is already found under Åbo. The Swedish forms follow the established city
# name where one exists (Tavastehus, Lahtis, Villmanstrand, Björneborg, Åbo, Karleby,
# Tammerfors, S:t Michel, Uleåborg) with -regionen; Jyväskylä has no Swedish name, so its region
# keeps the Finnish stem. A native reader should check the coined -regionen forms.
REGIONS = [
    dict(name="Pääkaupunkiseutu", sv="Huvudstadsregionen", en="Capital region",
         cities=["Helsinki", "Espoo", "Vantaa", "Kauniainen"]),
    # Vihti added 2026-09-18, on the maintainer's decision. Nummela was already here and
    # Nummela is a locality of Vihti municipality, a dozen kilometres by road from Vihdin
    # Kino, so a reader opening this row got Kino Akseli and not the other cinema in the
    # same municipality. Vihdin Kino's accent clears the floor in the row it now enters:
    # 14.9 dE00 on the weakest model against BioRex, 26.0 to normal vision.
    #
    # Vihti is conventionally Länsi-Uusimaa, and a row of that name would also pick up
    # Karkkila and Tammisaari. These rows are commuting areas rather than maakunnat, so
    # that is its own decision with its own accent measurements and it did not block this.
    dict(name="Keski-Uusimaa", sv="Mellersta Nyland", en="Central Uusimaa",
         cities=["Järvenpää", "Nurmijärvi", "Hyvinkää", "Kerava", "Nummela", "Vihti"]),
    # Sipoo stretches Itä-Uusimaa further than any other area is stretched, and is kept
    # because the cinema city it is nearest to is Porvoo rather than Loviisa.
    dict(name="Itä-Uusimaa", sv="Östra Nyland", en="Eastern Uusimaa",
         cities=["Porvoo", "Sipoo", "Loviisa"]),
    dict(name="Hämeenlinnan seutu", sv="Tavastehusregionen", en="Hämeenlinna region",
         cities=["Hämeenlinna", "Riihimäki"]),
    dict(name="Lahden seutu", sv="Lahtisregionen", en="Lahti region",
         cities=["Lahti", "Järvelä"]),
    dict(name="Kymenlaakso", sv="Kymmenedalen", en="Kymenlaakso",
         cities=["Kotka", "Kouvola"]),
    dict(name="Lappeenrannan seutu", sv="Villmanstrandsregionen", en="Lappeenranta region",
         cities=["Lappeenranta", "Imatra"]),
    dict(name="Mikkelin seutu", sv="S:t Michelsregionen", en="Mikkeli region",
         cities=["Mikkeli", "Puumala"]),
    dict(name="Tampereen seutu", sv="Tammerforsregionen", en="Tampere region",
         cities=["Tampere", "Kangasala"]),
    dict(name="Porin seutu", sv="Björneborgsregionen", en="Pori region",
         cities=["Pori", "Kankaanpää", "Huittinen"]),
    # Kaarina, Lieto and Naantali added 2026-10-04 on the maintainer's decision: 6 cinemas
    # across 4 chains against 3 across 2.
    dict(name="Turun seutu", sv="Åboregionen", en="Turku region",
         cities=["Turku", "Raisio", "Kaarina", "Lieto", "Naantali"]),
    dict(name="Jyväskylän seutu", sv="Jyväskyläregionen", en="Jyväskylä region",
         cities=["Jyväskylä", "Muurame", "Petäjävesi", "Äänekoski"]),
    dict(name="Kokkolan seutu", sv="Karlebyregionen", en="Kokkola region",
         cities=["Kokkola", "Pietarsaari"]),
    # Added 2026-10-04 on the maintainer's decision: 3 cinemas across 3 chains.
    dict(name="Oulun seutu", sv="Uleåborgsregionen", en="Oulu region",
         cities=["Oulu", "Muhos"]),
    dict(name="Meri-Lappi", sv="Havslappland", en="Sea Lapland",
         cities=["Kemi", "Tornio"]),
]

REGION_KEYS = ("name", "sv", "en", "cities")


def frontend():
    """The subset the client needs. Nothing about where a provider runs leaks out."""
    return [{**{k: p[k] for k in FRONTEND_KEYS},
             **{k: p[k] for k in FRONTEND_OPTIONAL if p.get(k)}} for p in PROVIDERS]


def regions():
    """The areas the client needs. `km` documents the cut and stays out of the JSON."""
    return [{k: r[k] for k in REGION_KEYS} for r in REGIONS]


def by_id(pid):
    return next((p for p in PROVIDERS if p["id"] == pid), None)


def modules(where=None):
    """Adapter modules to run, in order, deduplicated (one module, several providers)."""
    out = []
    for p in PROVIDERS:
        if not p["module"]:
            continue
        if where and p["where"] != where:
            continue
        if p["module"] not in out:
            out.append(p["module"])
    return out


if __name__ == "__main__":
    import sys
    if "--cloud" in sys.argv:
        print("\n".join(modules("cloud")))
    elif "--local" in sys.argv:
        print("\n".join(modules("local")))
    else:
        print("\n".join(f"{p['id']}\t{p['where']}\t{p['module'] or '-'}" for p in PROVIDERS))
