# This Week at Rochester

## Publishing contract

- Coverage: Thursday through the following Thursday, inclusive; America/New_York time.
- Stable live page: https://rochesterrizzo.github.io/Rizzo-Hours/this-week-at-rochester/
- Publish directly to `main` when running the authorized weekly sweep. Read the latest branch and files first.
- Archive the previous dated `index.html` under `archive/YYYY-MM-DD.html`, fixing relative navigation, before replacing it. Update `archive/index.html`.
- Preserve the current visual design. Include 3–7 **STAFF PICKS**, chronological day headings, category labels, direct original links, verified admission/registration information, and **SOURCE HEALTH** notes.
- In the root `index.html`, replace only the `<div class="rochester-week">` runner block immediately before `<div class="mooings">`. Preserve all unrelated content and office hours.
- Keep a dated structured event snapshot and a linked `class-update-teaser.html` for the existing Rochester events placeholder in the user's Word announcements. Do not rewrite class documents that were not supplied for editing.
- Verify dates, internal links/anchors, homepage scope, remote commit, and the live GitHub Pages result. Report any publishing failure precisely.
- Publish before the separately authorized email. A mail failure must not block a completed site update. Do not treat an automation trigger timestamp as proof that the sweep completed.

## Source registry

Use original event pages for final details. Add newly useful sources here. This registry is a starting point, not a closed list.

| Coverage | Source | Retrieval notes |
| --- | --- | --- |
| Main University calendar | https://events.rochester.edu/ | Public Localist API: `https://events.rochester.edu/api/2/events?start=YYYY-MM-DD&end=YYYY-MM-DD&pp=100&page=1`. Follow `page.next_page` until complete. End is exclusive: request through Friday to include the second Thursday. Use `event_instances[].event_instance.start/end`, `location_name`, `room_number`, `free`, `ticket_cost`, `has_register`, `description_text`, and `localist_url`. |
| All varsity sports | https://uofrathletics.com/calendar | Read each sport's current official schedule; the composite calendar can be empty in text retrieval. The site calendar service at `https://uofrathletics.com/services/responsive-calendar.ashx?type=month&sport=0&location=all&date=M/D/YYYY%2012:00:00%20AM&year=YYYY` is useful for finding every sport before verifying direct schedule pages. Emphasize home games, label away games, and verify opponents, times, venues, cancellations, and season year. Fall schedules include football, field hockey, both soccer teams, volleyball, both cross-country teams, both tennis teams, golf, rowing, swimming, and squash; also check other varsity sports for posted events. |
| Student activities / CCC | https://ccc.rochester.edu/ | Search direct organization and RSVP pages; sign-in-only venues must be marked as such. The public CampusGroups service at `https://ccc.rochester.edu/mobile_ws/v17/mobile_events_list?range=0&limit=200&filter8=YYYY-MM-DD&filter9=YYYY-MM-DD&order=&search_word=` provides broad date-window discovery; follow the returned organization and event URLs for verification. Do not infer that a thin organization homepage means no events. |
| Late Night / Wilson Commons | https://ccc.rochester.edu/latenight/ | Good source for trivia, live music, games, and weekend student events. Follow individual event links. |
| Eastman | https://www.esm.rochester.edu/events/ | Date filter: `?_esm_events_date_range=YYYY-MM-DD`; inspect direct `/esm-event/` pages. Distinguish public concerts from Eastman-only masterclasses. Check postponements. |
| River Campus music | https://www.sas.rochester.edu/mur/ensembles/concerts.html | Arthur Satz Department of Music calendar; complements Eastman. |
| Economics | https://www.sas.rochester.edu/eco/ | Check department announcements, `news-events/calendar.html`, and `news-events/workshops.html` plus each workshop page. Standing weekly times alone do not confirm a particular week's event. |
| Wallis | https://www.wallis.rochester.edu/events/seminar.html | Use current academic year, not historical tables below it. |
| Simon | https://simon.rochester.edu/events | Include relevant on-campus and online events; distinguish out-of-town alumni gatherings. |
| Humanities Center | https://www.sas.rochester.edu/humanities/ | Cross-check central calendar and direct event listings. |
| Goergen Institute for Data Science and AI | https://www.hajim.rochester.edu/dsc/ | Cross-check central calendar, panels, research fairs, and seminars. |
| River Campus Libraries | https://events.rochester.edu/group/river_campus_libraries/calendar | Workshops, talks, exhibits, and informal programs. |
| International Theatre Program | https://www.sas.rochester.edu/theatre/productions/index.html | Direct production pages, ticketing, and `productions/todd-talks.html`. Generic special-event pages can carry prior-year material. |
| Dance and Movement | https://www.sas.rochester.edu/dan/news-events/calendar.html | Dynamic widget can look empty; cross-check central calendar and program newsletter. |
| Sloan Performing Arts Center | Theatre production pages and central venue listings | Confirm Smith Theatre versus Todd or other venues. |
| Memorial Art Gallery | https://mag.rochester.edu/ | Direct event/exhibition pages; museum admission, special tickets, and opening hours differ. |
| Meliora Weekend | https://www.rochester.edu/melioraweekend/schedule/ | Full program uses a Cvent embed. Check registration/availability; never guess headliner times from promotional pages. |

## Known source issues observed October 8, 2026

- The University calendar API returned 134 raw listings across two pages for October 8–15; full pagination remains necessary.
- CCC's public service returned 63 listings in the window, but some direct CampusGroups pages still hide venue details behind sign-in. Label those venues as unavailable rather than guessing.
- Eastman's calendar exposed 24 public listings in the window. The George Abraham 90th-birthday concert appeared separately on Eastman and the University calendar as the same Wilmot Cancer Institute benefit and must be deduplicated.
- The athletics calendar service and the individual official schedules agreed on 11 varsity events in the window, including home/away status.
- MAG marked the October 8 Kirigami workshop, October 9 pottery workshop, and October 15 Hugo McCloud curator tour sold out. Keep notable sold-out events only when the status is explicit.
- Arthur Satz Music was active but had no River Campus concert in the October 8–15 window; its next posted concert was October 18. GIDS-AI and Dance/Movement likewise had no separately confirmed public event for this window.
- Search snippets can display the wrong timezone. Normalize authoritative source timestamps to America/New_York.
- Do not conflate missing/blocked/dynamic feeds with verified absence of events.
