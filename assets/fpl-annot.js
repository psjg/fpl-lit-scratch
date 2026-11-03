/*
 * fpl-annot.js: the facts of a published literate page, in its margin.
 *
 * The page's fact sidecar (<stem>.facts.json, shipped beside it) is drawn
 * as underlined spans, each with a card in the right margin at the height
 * of its span and a line between the two; a reader selects text, writes a
 * note and picks labels in a card at that height, and the row is kept in
 * this browser until it is exported and imported into the sidecar by lit.
 * Nothing is sent anywhere.
 *
 * Where a page is. The script's own URL ends in assets/fpl-annot.js, and
 * the directory above assets/ is the site root, so the page's repo path
 * (its item) is its URL below that root with .html read as .md. This
 * works on the published site (<meta name="fpl-site">) and on a local
 * serve of .site alike. The commit is <meta name="fpl-commit">, the HEAD
 * the page was rendered from (essay.lua).
 *
 * A row, as lit facts --import reads it:
 *
 *   { id: "a-" + base36 time + random, item, commit, by,
 *     text,            the selection as shown, whitespace made one space
 *     prefix, suffix,  32 characters of shown text either side of it
 *     labels: [], note, targets: [], createdAt, updatedAt }  (times in ms)
 *
 * by is who wrote the row: the name this browser was given under Naam
 * in the bar's menu (localStorage["fpl-annot:by"]), or, for a row an agent
 * imported with lit, that agent's model id; a row without one shows no
 * author, never a "?". A reply is a row without text whose first target
 * is the fact it answers: a message in its card's thread, one step in.
 *
 * A quote row has no offsets: lit finds it in the raw page by text, and
 * prefix and suffix choose among several hits. Rows of the sidecar keep
 * their own shape and are drawn by their text the same way. A row without
 * text is a fact about its first target: it is shown on the card of the
 * span it hangs from, nested under the fact it is about. When that target
 * is not a row but an address on the page (a block, sentence, clause or
 * code line: essay.lua and fpl-nav.js give them ids such as
 * strings-and-comments/b5l12), the row gets a card of its own at that
 * element, with a line to it. A click on a block's or sentence's number
 * puts that address in the URL and on the clipboard and, in the
 * kantlijn stand, opens the editor for a fact on it: the way a lawyer
 * cites a clause.
 *
 * Storage. localStorage["fpl-annot:" + item] holds a JSON array of this
 * browser's rows for that page; the sidecar is never written here. The
 * menu's Exporteer rijen downloads that array as <stem>.annot.json
 * (JSON.stringify(rows, null, 1)) and shows the lit command that takes
 * it in; Importeer rijen merges a file of rows into it by id; Wis mijn
 * rijen empties it, after asking. Exporteer logboek waits for the log.
 *
 * Finding a quote. The page's text nodes are read into one string, the
 * shown text: a backtick dropped, a curly quote read as a straight one,
 * every run of space or "|" one space, each character remembering the
 * node and offset it came from. A row's text is read the way lit reads
 * markdown (`name' as name, [text](url) as text, heading marks dropped)
 * and searched for in it; found once it is drawn, more than once it is
 * dubbel, nowhere stale. Both get one amber line at the top of the
 * margin that says so, not a span.
 *
 * A saved copy. A page saved with its overlay (the snapshot artifact PSJ
 * annotates) has no site URL and no sidecar beside it; it sets
 * window.FPL_SNAPSHOT = { item, commit, rows } before this script, and
 * the overlay runs on that instead.
 *
 * The margin. Quarto's right column (#quarto-margin-sidebar) is empty
 * once fpl-nav.js has moved the page's sections to the left, and holds
 * the cards; the margin starts RAIL (12px) past the text column, under
 * the bar's left edge, and ends RIGHT (24px) from the window's, at most
 * a CARD and the gutter's 28px wide. From 1380px wide fpl-annot.css
 * lets the right side of Quarto's grid take room from the left, so that
 * at 1440 the column stands at x320 and the bar (344px) and a card
 * (316px) fit, as on the boards. Where the column is hidden or a card
 * there would be narrower than NARROW (220px), each card folds under the block
 * its span is in, and the editor is a popover.
 * A card stands at the height of its span's last line, in the order of
 * those lines, and is only pushed down, by the card above it; the
 * editor is a card in that stack and pushes the rest down, never over
 * them. Its line stays in the gutter: a stub at the text's edge, then
 * one curve to the card's dot, so no two lines cross and none crosses
 * the text. A span over three lines or more gets a thin bar in the
 * gutter instead of an underline on every line. A quote in a card is
 * one line and a note two, until the card is hot (its span, knob,
 * line or card under the mouse, all lit together) or holds the focus;
 * a hot card opens over the one below it, so nothing moves. A card's
 * colour is its dot's. A clause's number shows only on the sentence
 * under the mouse, above the clause.
 *
 * A card (board F) is headed by the first words of its quote, never an
 * id, and its kind as a chip; its Graph and ⋯ keep their room while
 * hidden and show on hover. Under the note one meta line: who, when
 * known, the relations by their other end's text, a decision of the
 * page's ledger (<stem>.decisions.tsv, ids L-<id>) as a chip whose click
 * opens the row in the card, and "n reacties". A card opened (a click,
 * its ⋯, its "n reacties") is laid out open and pushes the rest down: its
 * thread, replies one step in, a reply arrow per message, and one field
 * Antwoord… whose Enter saves a reply row; past four messages the thread
 * folds to "n reacties". The ⋯ menu stands left of its card: Verbind
 * met… (key l; the knob's drag under the mouse), Graph van deze kaart,
 * Toon beide, Pak, Groepeer…, Verwijder (a sidecar row says why not,
 * under the mouse).
 *
 * The knob (board C) at the end of a span is a handle: a plain dot that
 * grows under the mouse, on focus and while carried, never a ring. Drag
 * it onto a span, card, fact or address (on touch after a long press):
 * the end under the pointer lights, and a dashed line from the span's
 * stub follows, in the gutter while the pointer is over the text and to
 * the pointer over the margin, a dot under the pointer. On the drop a
 * chooser asks the kind: verbindt (relates, also Enter), steunt, valt
 * aan, zelfde als, citeert (keys 1-5); Esc or a click elsewhere lets go.
 * A drop on nothing or on its own span lets go and says so. A click on
 * the knob, its card's Verbind met… or the key l (on the knob or card
 * with the focus, else the card under the mouse) arms a pick instead: a
 * click on the other end, or Tab and the arrows to it and Enter, asks the
 * same. The row is saved as every pick's is, targets [start, end].
 *
 * The same knob stretches (board D): carried along the text of its own
 * block rather than onto another end, it moves the end of a span of this
 * browser a whole word at a time, the words gained washed and dashed,
 * the words lost washed grey, and a tip "+ n woorden · loslaten bewaart
 * · Esc zet terug"; the drop saves text, prefix and suffix read anew,
 * Esc puts it back. Where it is let go decides: over another span, card,
 * fact or knob, or another block's text, it connects. A bundle's knob
 * stretches the piece it ends; a sidecar span only connects, and says
 * why. Shift with the arrows on a focused knob stretches by a word, Enter
 * saves.
 *
 * The bar. One bar, fixed above the margin column, holds the three
 * stands as tabs (Lezen, Spans, Kantlijn, also the key "a"), the search
 * field (the key "/" in Kantlijn; elsewhere / stays Quarto's site search,
 * as f and s always do), the menu Weergave (Kaarten, Graph, Boom: what
 * stands beside the text; not Kantlijn, the stand's name, and Graph and
 * Boom off on a page with no row and no chunk) and a menu ⋯: Naam,
 * Importeer rijen, Exporteer rijen, Exporteer logboek, Vouw tot de
 * spans, Context 0-3, Sneltoetsen (also "?") and Wis mijn rijen; what
 * an item would act on, or why it cannot, shows under the mouse. No
 * line counts anything on screen (QA, block 4): the counts are read
 * out to a screen reader only (role status), a lost row is its strip,
 * and a filter lights the funnel at the field's right end, which opens
 * the label and layer filters as a panel; a click into the field only
 * types, hover opens nothing, and nothing in the bar changes size or
 * place on hover or on a change of stand.
 *
 * The filter panel (board V4a). First the layers, four buttons:
 * Argument, Coref, Topic-focus and Progressie (keys 1-4 outside Lezen),
 * each saying its key and Shift-klik under the mouse, and a (?) by the
 * heading that says what each draws; under them, after Ook, Markeringen
 * and Draden, which are no layer to read by but the spans and the
 * threads (one list holds one kind). A click turns a layer on or off;
 * Shift-click (Shift+1-4) shows it alone, the others, the threads and
 * (but for Argument, drawn on them) the markings off and the text
 * dimmed (board V4b: what the old lenses were), and again shows all.
 * Markeringen off leaves the marks in the text as anchors, unpainted,
 * and takes their cards from the margin. Then the labels: a field over their scopes, the list
 * one level at a time with how many spans carry each; up and down
 * choose, right goes a level deeper, left back up, Enter or a click
 * strikes a label and all under it, Shift shows it alone. A label of
 * MEANING has a (?) that says what it means; any other has none. A
 * relation is shown by its Dutch name (omdat, citeert, spreekt tegen),
 * here as on a card and in the graph; its English key is the label
 * written and queried. The
 * panel holds no sentence of explanation: what a control does it shows. Where Quarto shows its top
 * bar (a narrow window) the bar folds into it, a stand picker and three
 * icons, the search and the counts in the filter panel; where neither
 * fits, the folded bar stands at the top right of the window. In
 * Kantlijn an empty margin says in three lines how to annotate,
 * connect and fold.
 *
 * Three stands: lezen shows nothing; spans underlines the spans whose
 * labels pass the filter, and a click on a span opens
 * its card alone; kantlijn shows every card, the lines and the editor.
 * localStorage["fpl-annot:mode"] keeps the stand
 * and "fpl-annot:hide" the labels switched off, for the whole site.
 *
 * Bands (after LiquidText's collapse, Tashman & Edwards, CHI 2011;
 * boards G and H). A band folds the blocks from one block address to
 * another, both ends included, into a seam of 28px: two hairlines
 * across the column and at their left its range, "1.2.1.3 §9 - 1.2.1.4
 * §7 · 25 blokken", so the reader sees where the text is folded and how
 * much, and the page stays one scroll. Headings, lists and tables
 * between the two blocks fold with them. A click on the seam (or Enter)
 * opens it, Escape the newest; under the mouse it darkens and a tip
 * under it says how to fold further. The bands are in the URL as
 * ?scrunch=a..b,c..d (block ids such as the-plan/b3) and in
 * localStorage["fpl-annot:scrunch:" + item]; at load the URL wins. A
 * span inside a band draws its line, and places its card, at the seam.
 *
 * Folding is a gesture, as in LiquidText. Shift+wheel over the text
 * folds around the pointer, the block under it first and then outward,
 * as far as the wheel turns, the seam staying under the pointer;
 * turned back it opens the band under the pointer (or the nearest in
 * the window). On a touch screen two fingers drawn together fold the
 * blocks between them, from the middle out, as many as the fingers
 * closed by; drawn apart over a band they open it. With a filter or a
 * query on, the same Shift+wheel folds to the spans they let through:
 * every block further than the context (0-3 blocks, the menu's
 * Context, kept in localStorage["fpl-annot:context"]) from such a span,
 * and back opens them; the screen reader hears "5 van 9 spans ·
 * ingevouwen tot de spans, context 1". Vouw tot de spans, in the menu,
 * does the same without the gesture; chosen again it opens them, and a
 * new context refolds. A card whose row points at another place on the
 * page has "Toon beide", which folds what lies between the two so both
 * are in view (its menu, or a click on the other end in its meta line).
 * A query asked lights the search field, whose / gives way to an x
 * that clears it.
 *
 * Close reading. Outside Lezen each block carries a bar in its left
 * gutter, the accent's blue in three steps by how many rows hang from it
 * (feedback 16: a grey of 3px went unseen; after Zyto 2012, where
 * the most annotated regions of a text showed where readers stumbled).
 * And j and k move a reading cursor sentence by sentence (after Miall
 * 1994): the sentence is washed, its address is the URL's hash, so a
 * reload returns to it, and Enter opens the editor for a fact on it.
 *
 * Arguments, after the Argument Interchange Format (Chesnevar et al.
 * 2006): a claim never points at a claim. A supports or attacks row
 * stands between them, read targets[0] -> targets[1:], and has an id of
 * its own, so an attacks row may aim at it: an undercut, which attacks
 * the inference rather than its premise. The data stays a graph (a
 * premise may serve two claims); a card shows the tree read from its
 * row, grounds under the claim, undercuts under the inference they
 * attack. Steunt and valt aan are kinds of the knob's chooser, and a
 * branch of a tree is an end like a span, a card or a fact.
 *
 * Layers, after the Prague Dependency Treebank's stacked annotation:
 * only a span anchors in the text, every other row names an id. A row's
 * layer is read from what it is, as lit's facts.layer reads it (span,
 * fact, thread, argument, tfa, coref, group, relation), and the filter
 * panel's buttons hide one (fact, group and relation have none); a resumes row, in lit's tfa layer, has its own
 * (Progressie). A coref row groups ids that name
 * one referent: hovering one lights the others. The tfa lens marks a
 * clause t (bound), c (bound, contrastive) or f (not bound), after the
 * t-layer manual (Mikulova et al. 2006): Alt-click a clause cycles its
 * value. A resumes row says a clause takes up an earlier one (Danes
 * 1974); Alt-Shift-click a clause arms the pick, and the left gutter
 * draws each such link as an arc, so the thematic progression shows.
 *
 * Labels are free paths, a name scoped by names to any depth (fn/claim,
 * slop/beeld/dood), after Marshall (1997: no fixed palette of marks)
 * and VIKI (Marshall et al. 1994: types arise from examples, structure
 * comes on demand). The
 * editor ranks the labels by use, on this page and in this browser across
 * the site, and shows the first six as chips; its field completes from
 * all of them. The seeds under fn/ and code/ (code/stijl, code/bug: who
 * found it is the row's by, not a label) only start the list and sink,
 * never go. Striking a scope in the filter strikes everything under it,
 * and each label there has a square of its colour. When three
 * rows on a page share a label, the margin offers it once as a quick
 * chip, one click in the editor of an address; nothing is imposed. Rows
 * on one address share one card, side by side; with different labels
 * they are readings, as Empson reads one passage several ways at once,
 * and so are facts on one span with different labels. A row that passes
 * the filter shows its group.
 *
 * Colours (boards V3, V4; feedback 17). A label's colour is a place on a
 * hue tree over the OKLCH wheel, colourOf below: dit, niet and slop keep
 * the hues of the review surface, every other root takes the middle of
 * the largest free gap in a fixed order and then in the order this
 * browser first meets it (kept site-wide), so a new scope never moves an
 * old colour; roots alternate two lightness bands and a child sits in an
 * arc round its parent, darker. A row is drawn in the colour of the kind
 * its card shows (a row with no label in the weave's green or blue): its
 * span, line, knob and dot. The spans over a stretch of text are its
 * layers, the longest outermost: the text is washed in the innermost
 * one's colour, 20% and 12% more per layer around it up to 70%, never
 * below 4.5:1 for the text, with a line per layer under it, the outermost
 * lowest. Under the mouse a span is outlined in its colour.
 *
 * The graph (boards V2b-V2d, V4d): every row of the page and everything
 * a row names, in the layers shown, as a plane beside the page. Graph in
 * the Weergave menu opens it, Kaarten there closes it; the text column slides to the
 * window's left edge, the left nav and the margin's cards give way, and
 * the bar heads the plane. A row is a card (board V2b): its kind on a
 * line (a label, besluit and its topic, weigering, test, chunk) over two
 * lines of its quote, a decision's words, or an id's words, never the id
 * (refusal:dedent%20below… reads "dedent below …"), and a span of a
 * lone glyph its start in the text, the glyph and the words after it;
 * the query and the filter dim cards here as in the margin. Beside the
 * word a shape says the kind without its colour (a span a square, a fact
 * a dot, a decision a bookmark, ...); every card has one thin solid
 * border.
 * The plane is drawn in layers, left to right: the spans in the first
 * column in page order, what is about them to their right, so every
 * edge runs one way and none crosses a card (see layered). A relation
 * row is a node, so an undercut has something to aim at (AIF): its
 * kind's sign (steunt a plus, valt aan a minus, spreekt tegen a struck
 * circle, ...) in a column of its own past its ends, its word above it
 * under the mouse; a fact stands right of what it is about; a tfa or
 * resumes row has no node.
 * The edges are typed (verbindt, steunt, valt aan, zelfde als, citeert),
 * and the chips at the plane's foot, each with its kind's sign, switch a
 * kind on and off; a (?)
 * at their end says what a click, a drag and Shift do. A card
 * drags, in this view only. The plane stands round one card, its
 * centre, showing it and its neighbours (feedback 25): the card it was
 * opened from (Graph on a card), else the card open in the margin;
 * opened from the bar with none, the whole page. Buurt and Hele pagina
 * at its head switch between the two. A click on a card makes it the
 * centre (beside the page, the page scrolls to its span too), a click
 * on the centre goes to its span; each step is an entry in the
 * browser's history, so Back and Forward walk the steps, Alt ← as
 * Back, and Back past the first closes the plane. Beside the rows stand the
 * page's chunks and the files they tangle to, from <stem>.graph.json
 * (lit graph, written at publish), behind the chip code: a chunk uses
 * chunks, tangles to a file, and a row may name a chunk. A window too
 * narrow for the plane beside the column gets it as a sheet.
 *
 * Discontinuous spans: a parts row bundles span rows as the pieces of
 * one span (Mueller 2005 keeps such a span as several token ranges). Its
 * pieces are underlined as before but light together and share one card,
 * the parts row's, where a fact about the whole hangs. Alt-select text to
 * add a piece, again for the next, and Enter bundles them; Esc stops.
 * The card lists the pieces as chips in order. On a parts row of ours
 * "Deel erbij…" arms the next Alt-selects to join that row, until Esc,
 * Enter or leaving Kantlijn, and text a shown bundle's piece covers is
 * refused; a chip's × lets its piece go as a loose span; with one piece
 * left the bundle goes (lit refuses a one-member set), and a fact on it,
 * kept, gets a lost card like any fact whose row is gone (the ask counts
 * them; lit refuses them until they name something).
 * A sidecar row's chips only read. A piece may be a bundle: Alt-select
 * text of another whole and that whole (the outermost) joins as one
 * piece. It has no card then; its whole's card shows it as one chip of
 * bracketed pieces, a click writes a fact about it, and its facts hang
 * there under "over deel <id>". lit keeps the bundles a tree.
 *
 * Groups (boards V3a, V3b, V3d): a set row whose first label is
 * group/<naam> puts rows together as one thing, its targets the members
 * (one at least: the tray may hold one sentence), with at most one
 * role/<rol> (claim, bewijs, tegen) and one order/<n> beside it; its
 * note is its name on screen. It has no card and no node: each member's
 * card carries the group as a chip, and the graph draws a frame round
 * its members, laid out as one block of cells with the row above it
 * empty for the frame's tab, which names the group and its role; a
 * card in two groups stands in the first one's block. Under the mouse a
 * chip or a frame lights the members, spans and cards, in a class of
 * their own (a hot card would open over the next). Shift-click cards in
 * the graph to choose them: a form asks a name and a role, and Enter
 * saves the row, or the cards join the group of ours with that name;
 * Groepeer… in a card's menu opens the graph with that card chosen and
 * the form open; the tab of a group of ours opens it there, to rename or let go, and
 * Esc lets a choice go before it closes the graph. group/gepakt is the
 * tray of pulled sentences, a group without a role: Pak in a card's
 * menu adds the card to it, Leg terug takes it out, and the row goes
 * with its last sentence. The labels of a group count for each member
 * in the filter, so group and role are scopes there.
 *
 * The tree (boards V3c, V4c): Boom in the menu, or b, turns the plane to
 * the groups as an argument, a block per group (the tray aside) in the
 * order of its order/<n>; with no group yet, one empty block and its
 * one action, Maak groep, which turns to the graph. A group hangs under another by a supports or
 * attacks row from it to the other, which gives the step its kind and
 * weight; a bewijs or tegen without one hangs under the last claim before
 * it, a thin grey line without a sign. An attacks row aimed at a step is
 * an undercut, a dashed block under the group whose step it attacks, its
 * line leaving the step's diamond. A line's thickness is its weight
 * (board V4c: 2, 2.75 and 3.5 for 2, 3 and 4), the digit shows under the
 * mouse, and the block's head has the weight as five dots: on a step of
 * ours a dot sets it, on a step without a row it writes one (supports for
 * bewijs, attacks for tegen). A click on a member jumps to it, Alt ←
 * back. The grip drags a block among the others, Alt with ↑ ↓ moves it
 * one, and every group is numbered order/1 on down as it then stands; a
 * group of the sidecar keeps its place, and the move is refused. At the
 * plane's foot the tray, group/gepakt: beside the tree the text keeps its
 * knobs (no cards, no lines), a knob dropped on the tray pulls its span
 * and on a block puts it in that group, a sentence dragged from the tray
 * onto a block joins the group and leaves the tray, and the tray's
 * sentences are dashed in the text while the tree is open. Graph in the
 * Weergave menu turns the plane back in place, Kaarten closes it.
 *
 * The coref lens: coref rows that share a member are one chain (a
 * union-find over the sets), numbered in page order, and each member on
 * the page carries its chain's number, as the PDT links an anaphor to its
 * antecedent (Mikulova et al. 2006, ch. 9) and a chain follows from the
 * links. Zelfde als in the knob's chooser joins its end to the chain.
 *
 * Querying across the layers (after PML-TQ, Pajas and Stepanek 2009):
 * the bar's search field takes terms [!]key:value, all to hold, in
 * groups apart by "|" of which one must hold, and has:R+N or gives:R+N
 * for a chain of at least N R edges; the same language as lit facts
 * --query (facts.parse_query, facts.query) and tested against the same
 * cases (tests/query_cases.json): what it finds stays, the rest fades.
 * A query that does not parse reddens the field, which says why under
 * the mouse; how many it found is read out; a query asked in Lezen turns to Spans, where there is
 * something to find.
 */
(() => {
  "use strict";
  const LABELS = ["reason", "claim", "question", "history", "slop", "good",
    "because", "supports", "attacks", "contradicts", "cites", "relates", "checkedBy",
    "resumes", "coref", "parts", "tfa/t", "tfa/c", "tfa/f",
    "fn/definition", "fn/example", "fn/transition", "fn/claim", "fn/evidence", "fn/aside", "fn/hedge",
    "code/stijl", "code/bug"];
  /**
   * What a label means, behind its (?) in the filter panel: one short
   * line each, edited freely. A label not here has no (?): its name
   * and its colour are all there is to say.
   */
  const MEANING = {
    dit: "Zo goed: houden", niet: "Zo niet: weg of anders", slop: "Lege of opgeblazen tekst",
    "slop/beeld": "Beeldspraak die niets draagt", "slop/beeld/dood": "Een dood beeld: cliché",
    waarom: "Hier ontbreekt het waarom", lang: "Te lang voor wat het zegt", verhaal: "Het verhaal hapert hier",
    anders: "Kan anders, beter", onduidelijk: "Niet te volgen", code: "Over de code",
    "code/stijl": "De code werkt, de vorm niet", "code/bug": "De code doet iets fout",
    claim: "Een bewering", reason: "Een reden", question: "Een vraag", history: "Hoe het zo kwam", good: "Goed zo",
    because: "Omdat: een besluit als reden", supports: "Steunt een bewering", attacks: "Valt een bewering aan",
    contradicts: "Spreekt tegen", cites: "Citeert", relates: "Verbindt, zonder soort", checkedBy: "Nagekeken door",
    resumes: "Neemt een eerdere bijzin op (Daneš)", coref: "Noemt hetzelfde", parts: "Delen van één span",
    group: "Hoort bij een groep", "group/gepakt": "Gepakte zinnen", role: "Wat een groep doet in het betoog", order: "Plaats van een groep",
    tfa: "Topic-focus van een bijzin", "tfa/t": "Gebonden: bekend", "tfa/c": "Gebonden, contrastief", "tfa/f": "Focus: nieuw",
    fn: "Wat een zin doet", "fn/definition": "Definieert", "fn/example": "Een voorbeeld", "fn/transition": "Een overgang",
    "fn/claim": "Beweert", "fn/evidence": "Bewijs", "fn/aside": "Terzijde", "fn/hedge": "Zwakt af",
    group: "Hoort bij een groep", role: "De rol in een groep", order: "De plaats in een groep",
  };
  const LABEL =/^[^/ \t\n\r\f\v]+(?:\/[^/ \t\n\r\f\v]+)*$/;   // lit's facts.LABEL, whitespace spelt out alike
  /** A label and every scope above it: fn/claim/strong gives fn, fn/claim, fn/claim/strong. */
  const scopes = (l) => l.split("/").map((_, i, a) => a.slice(0, i + 1).join("/"));
  /** Whether a label lies at or under a scope. */
  const under = (l, p) => l === p || l.startsWith(p + "/");
  const store = (k, d) => (set) => {
    try {
      if (set !== undefined) localStorage.setItem(k, JSON.stringify(set));
      return JSON.parse(localStorage.getItem(k) || "null") ?? d;
    } catch { return set ?? d; }
  };
  const tally = store("fpl-annot:used", {});        // label -> times saved in this browser, site-wide
  const quick = store("fpl-annot:quick", []);       // labels confirmed as quick chips
  const declined = store("fpl-annot:declined", []); // labels whose offer was turned down

  /*
   * The colour of a label: a tree over the OKLCH wheel (feedback 17).
   * dit, niet and slop keep the hues of the review surface's colours;
   * every other root takes the middle of the largest free arc, in the
   * order of HUES and then of first sight in this browser
   * (localStorage["fpl-annot:hues"], site-wide), so a new scope never
   * moves an old one. Roots alternate two lightness bands; a child takes
   * the middle of the largest free stretch of an arc around its parent's
   * hue (the first child sits on it), each level down darker and greyer.
   * The tree is drawn for a light page; a dark one gets the same hues.
   */
  /* the OKLCH hues of #1d7a46, #c0392b and #b8620a as tree.py reads them, to the last digit: a tie between two gaps
     falls the way it fell for the boards */
  const ANCHORS = { dit: 153.69175324544503, niet: 29.696698619015162, slop: 56.519342372371014 };
  const HUES = ["waarom", "lang", "verhaal", "code", "anders", "onduidelijk", "group", "role", "fn", "claim", "note", "order",
    "coref", "tfa", "resumes", "supports", "attacks", "slop/beeld", "slop/beeld/dood", ...LABELS];   // the boards' slop chain
  const BANDS = [0.52, 0.64], ARC = 12;   // OKLCH lightness of even and odd roots; a child's arc, in degrees either side
  const sighted = store("fpl-annot:hues", []);
  /** OKLCH to linear sRGB (Ottosson 2020). */
  const lrgb = (L, C, h) => {
    const a = C * Math.cos(h * Math.PI / 180), b = C * Math.sin(h * Math.PI / 180);
    const l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3, m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3,
      s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3;
    return [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s, -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
      -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s];
  };
  /** An OKLCH colour as #rrggbb, its chroma lowered until sRGB holds it (at none, a grey of its lightness). */
  const hex = (L, C, h) => {
    let c = lrgb(L, C, h);
    while (C > 0 && c.some((v) => v < -1e-4 || v > 1 + 1e-4)) c = lrgb(L, C = Math.max(0, C - 0.002), h);
    const enc = (x) => (x = Math.min(1, Math.max(0, x)), x <= 0.0031308 ? 12.92 * x : 1.055 * x ** (1 / 2.4) - 0.055);
    return "#" + c.map((v) => Math.round(enc(v) * 255).toString(16).padStart(2, "0")).join("");
  };
  const lin = (x) => (x /= 255, x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4);
  /** #rrggbb or rgb()/rgba() as three numbers 0-255. */
  const rgbOf = (s) => s.startsWith("#") ? [1, 3, 5].map((i) => parseInt(s.slice(i, i + 2), 16)) : s.match(/[\d.]+/g).slice(0, 3).map(Number);
  /** WCAG's contrast of two colours. */
  const contrast = (x, y) => {
    const Y = (s) => { const [r, g, b] = rgbOf(s).map(lin); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const [a, b] = [Y(x), Y(y)].sort((p, q) => q - p);
    return (a + 0.05) / (b + 0.05);
  };
  /** A fraction p of colour c over the ground g, as #rrggbb. */
  const mix = (c, p, g) => { const [x, y] = [rgbOf(c), rgbOf(g)];
    return "#" + x.map((v, i) => Math.round(y[i] + (v - y[i]) * p).toString(16).padStart(2, "0")).join(""); };
  const hue = new Map(Object.entries(ANCHORS)), roots = Object.keys(ANCHORS);
  /** Degrees mod 360 as Python's %, which tree.py used: a remainder, then one turn added only when it is negative. */
  const mod = (x) => { const m = x % 360; return m < 0 ? m + 360 : m; };
  /** Place a scope, its parent first: the middle of the largest gap among its placed siblings, on the wheel or in the parent's arc. */
  function placeHue(p) {
    if (hue.has(p)) return;
    const cut = p.lastIndexOf("/"), up = cut < 0 ? null : p.slice(0, cut);
    if (up) placeHue(up);
    const sibs = [...hue].filter(([k]) => (k.lastIndexOf("/") < 0 ? null : k.slice(0, k.lastIndexOf("/"))) === up).map(([, h]) => h);
    const a = up && ARC / 2 ** (p.split("/").length - 2), hs = (up ? [hue.get(up) - a, hue.get(up) + a, ...sibs] : sibs).sort((x, y) => x - y);
    let best = [-1, 0];
    for (let i = 0; i < hs.length - (up ? 1 : 0); i++) {
      const g = up ? hs[i + 1] - hs[i] : mod(hs[(i + 1) % hs.length] - hs[i]) || 360;
      if (g > best[0] || (g === best[0] && hs[i] > best[1])) best = [g, hs[i]];   // a tie to the later start, as tree.py's max()
    }
    if (!up) roots.push(p);
    hue.set(p, up ? best[1] + best[0] / 2 : mod(best[1] + best[0] / 2));   // a child's hue stays unwrapped, so its own arc sorts
  }
  for (const s of [...HUES, ...sighted()].flatMap(scopes)) placeHue(s);
  /** The colour of a label; a scope new to this browser is remembered where it landed. */
  function colourOf(label) {
    const fresh = scopes(label).filter((s) => !hue.has(s));
    if (fresh.length) { fresh.forEach(placeHue); sighted([...sighted(), ...fresh]); }
    const d = label.split("/").length - 1;
    // eight levels down the band would reach black: a deep label stops at 0.2 and grey
    const L = BANDS[roots.indexOf(label.split("/")[0]) % 2] - 0.08 * d;
    return hex(Math.max(0.2, L), Math.max(0, 0.13 - 0.02 * d), hue.get(label));
  }
  window.fplAnnotColour = colourOf;   // for the headless tests, and a console
  // the layers drawn by CSS (tfa washes, resumes arcs, chain numbers) take the colours their buttons show
  for (const k of ["coref", "tfa", "resumes", "group", "role", "supports", "attacks"]) document.documentElement.style.setProperty(`--fpl-${k}`, colourOf(k));
  const LAYERS = ["span", "fact", "thread", "argument", "tfa", "coref", "group", "relation"];
  // one Dutch name per relation, wherever one is shown (a chip, the label list, the graph, a meta line); the English key
  // stays the label as written and as queried (QA, block 4: the panel said contradicts where the card said spreekt tegen)
  const VERB = { supports: "steunt", attacks: "valt aan", contradicts: "spreekt tegen", because: "omdat", cites: "citeert",
    checkedBy: "getoetst door", resumes: "neemt op", supersedes: "vervangt", coref: "zelfde als", relates: "verbindt" };
  const RELATIONS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "relates", "resumes"]);
  const AROUND = 32;
  // a card is no text of the page: a narrow margin folds its cards in under their blocks, in main, and a redraw that read
  // their quotes found every span twice (QA, block 4: a layer alone at 760 made six spans dubbel)
  const SKIP = "script, style, button, .fpl-annot-ui, .fpl-card";
  const QUOTE = { "‘": "'", "’": "'", "“": '"', "”": '"' };
  const GAP = 12;
  const HEAD = 19;   // a card's top to the middle of its first row: its border, padding and half the row
  const LONG = 56;   // px: an address taller than this (a block, one rect) is long, as a span over three lines is
  const CARD = 360;  // px: the widest a card in the margin gets
  const NARROW = 220;   // px: the narrowest; below it the cards fold in under their blocks (a card of one word a line, feedback 17)
  const RAIL = 12;   // px: from the text column's edge to the margin (the bar's left edge); a card stands 28px further in
  const RIGHT = 24;  // px: from the margin's right edge to the window's

  const snap = window.FPL_SNAPSHOT;
  const root = snap ? "" : new URL("../", document.currentScript.src).href;
  const here = location.href.split(/[?#]/)[0];
  const meta = (name) =>
    document.querySelector(`meta[name="${name}"]`)?.content ?? "";
  const commit = snap?.commit ?? meta("fpl-commit");
  if (!snap && (!here.startsWith(root) || !here.endsWith(".html") || !commit)) return;
  const page = snap ? snap.item.replace(/\.md$/, ".html") : decodeURIComponent(here.slice(root.length));
  const item = page.replace(/\.html$/, ".md");
  const stem = page.slice(page.lastIndexOf("/") + 1, -".html".length);
  const key = "fpl-annot:" + item;
  const body = document.querySelector("main") || document.body;
  const column = document.getElementById("quarto-margin-sidebar");

  let sidecar = [];

  const MODES = ["lezen", "spans", "kantlijn"];
  const NONE = "zonder label";
  const mode = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:mode", set);
      const m = localStorage.getItem("fpl-annot:mode");
      return MODES.includes(m) ? m : "lezen";
    } catch { return set ?? "lezen"; }
  };
  const hidden = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:hide", JSON.stringify([...set]));
      return new Set(JSON.parse(localStorage.getItem("fpl-annot:hide") || "[]"));
    } catch { return set ?? new Set(); }
  };

  /*
   * The layers a reader turns on and off (board V4a): four to read the
   * text by, keys 1-4, then the spans and the threads. A key is a row's
   * layer as lit reads it, except Progressie: lit counts a resumes row
   * in the tfa layer, here it has a button of its own (sheetOf).
   */
  const SHEETS = [["argument", "Argument"], ["coref", "Coref"], ["tfa", "Topic-focus"], ["resumes", "Progressie"],
    ["span", "Markeringen"], ["thread", "Draden"]];   // not Spans: that is a stand
  const FOUR = SHEETS.slice(0, 4).map(([k]) => k);
  /** The layers switched off, site-wide; a key of an older panel (fact, relation) has no button and counts for nothing. */
  const offLayers = (set) => {
    try {
      if (set) localStorage.setItem("fpl-annot:layers", JSON.stringify([...set]));
      return new Set(JSON.parse(localStorage.getItem("fpl-annot:layers") || "[]").filter((k) => SHEETS.some(([s]) => s === k)));
    } catch { return set ?? new Set(); }
  };
  /** The one of the four shown alone (Shift-click, Shift+1-4): the others and the threads off; else null. */
  const alone = () => { const o = offLayers(), on = FOUR.filter((k) => !o.has(k)); return on.length === 1 && o.has("thread") ? on[0] : null; };

  /** This browser's rows for the page; [] when none or unreadable. */
  const local = () => {
    try { return JSON.parse(localStorage.getItem(key) || "[]"); }
    catch { return []; }
  };
  const keep = (rows) => localStorage.setItem(key, JSON.stringify(rows));
  const by = (set) => {
    try { if (set != null) localStorage.setItem("fpl-annot:by", set); return localStorage.getItem("fpl-annot:by") || ""; }
    catch { return set ?? ""; }
  };

  /** A markdown text as lit's plain() shows it (facts.py MARKUP). */
  const plain = (s) => s
    .replace(/`([A-Za-z_][\w.]*)'/g, "$1").replace(/`/g, "")
    .replace(/’/g, "'").replace(/\[([^\]\n]*)\]\([^)\s]*\)/g, "$1")
    .replace(/^#+[ \t]+/gm, "").replace(/[\s|]+/g, " ");

  /**
   * The shown text of the page body: flat, and for each of its characters
   * the [node, offset] it came from.
   */
  function shown() {
    const walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => n.parentElement.closest(SKIP)
        ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
    });
    let flat = "", space = true;
    const from = [];
    for (let n; (n = walk.nextNode());) {
      for (let i = 0; i < n.data.length; i++) {
        let c = n.data[i];
        if (c === "`") continue;
        if (/[\s|]/.test(c)) {
          if (space) continue;
          c = " ";
        }
        space = c === " ";
        flat += QUOTE[c] ?? c;
        from.push([n, i]);
      }
    }
    return { flat, from };
  }

  /** Where a row's text is shown: [start, end), or "dubbel" or "stale". */
  function find(ix, row) {
    const want = plain(row.text);
    let hits = [];
    for (let i = ix.flat.indexOf(want); i >= 0; i = ix.flat.indexOf(want, i + 1))
      hits.push(i);
    if (hits.length > 1) {
      const pre = plain(row.prefix ?? ""), suf = plain(row.suffix ?? "");
      hits = hits.filter((i) => ix.flat.endsWith(pre, i)
        && ix.flat.startsWith(suf, i + want.length));
    }
    if (hits.length === 1) return [hits[0], hits[0] + want.length];
    return hits.length ? "dubbel" : "stale";
  }

  /** Wrap shown characters [s, e) in marks, one per text node they cross. */
  function wrap(ix, s, e, row) {
    const cuts = [];
    for (let i = s; i < e; i++) {
      const [n, o] = ix.from[i], last = cuts[cuts.length - 1];
      if (last && last[0] === n) last[2] = o + 1;
      else cuts.push([n, o, o + 1]);
    }
    for (const [n, a, b] of cuts) {
      const r = document.createRange(), m = document.createElement("mark");
      r.setStart(n, a);
      r.setEnd(n, b);
      m.className = `fact fact-${row.mine ? "mine" : "vers"}`;
      m.dataset.id = row.id;
      r.surroundContents(m);
    }
  }

  const el = (tag, props = {}, ...kids) => {
    const e = Object.assign(document.createElement(tag), props);
    e.append(...kids.filter((k) => k != null && k !== false));
    return e;
  };
  const button = (text, onclick, className = "") =>
    el("button", { type: "button", onclick, className }, text);
  const marksOf = (id) => body.querySelectorAll(`mark.fact[data-id="${CSS.escape(id)}"]`);
  /** What a row is drawn at: its marks, or the addressed element it is about. */
  /** The shown parts row a span row is a piece of, or undefined. */
  const partsOf = (id) => all.find((r) => r.labels?.[0] === "parts" && shows(r) && r.targets?.includes(id));
  const bundleOf = (id) => all.find((r) => r.id === id && r.labels?.[0] === "parts");
  /** The outermost shown whole a row is a piece of, through bundles in bundles, or undefined. */
  const wholeOf = (id) => {
    let w;
    const seen = new Set([id]);
    for (let p = partsOf(id); p && !seen.has(p.id); p = partsOf(p.id)) { w = p; seen.add(p.id); }
    return w;
  };
  /** A parts row and every id inside it, bundles in it and their pieces, in order (lit refuses a ring; this stops at one). */
  const treeOf = (pr, seen = new Set([pr.id])) => [pr.id, ...(pr.targets ?? []).flatMap((t) => {
    const q = bundleOf(t);
    return !q ? [t] : seen.has(t) ? [] : (seen.add(t), treeOf(q, seen));
  })];
  /** The span rows a parts row is made of, through the bundles in it. */
  const leavesOf = (pr) => treeOf(pr).filter((t) => !bundleOf(t));
  /** A whole and everything in it, from any of its ids; else just the id. */
  const groupOf = (id) => {
    const p = bundleOf(id), w = wholeOf(id) ?? p;
    return w ? treeOf(w) : [id];
  };
  /**
   * A named group (boards V3a-V3d): a set row, group/<naam> its first
   * label, with role/<rol> and order/<n> beside it; its targets are its
   * members, never a fact about the first. group/gepakt is the tray of
   * pulled sentences, a group without a role. Its name on screen is its
   * note, else the name in its label.
   */
  const TRAY = "group/gepakt";
  const isGroup = (r) => /^group\//.test(r?.labels?.[0] ?? "");
  const groupName = (g) => g.note?.trim() || (g.labels[0] === TRAY ? "Gepakte zinnen" : g.labels[0].slice(6).replace(/-/g, " "));
  const roleOf = (g) => g.labels.find((l) => l.startsWith("role/"))?.slice(5) ?? "";
  /** The shown groups that hold an id, or the whole it is a piece of. */
  const groupsOf = (id) => { const w = wholeOf(id)?.id;
    return all.filter((r) => isGroup(r) && shows(r) && r.targets?.some((t) => t === id || t === w)); };
  /** A group's name as a label: lower case, no accents, words joined by "-". */
  const slug = (name) => name.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "");
  function anchorsOf(id) {
    const pr = bundleOf(id);
    if (pr) return leavesOf(pr).flatMap((t) => [...marksOf(t)]);   // a discontinuous span: its pieces' marks
    const ms = marksOf(id);
    if (ms.length) return [...ms];
    const row = all.find((r) => r.id === id);
    const at = row && typeof row.text !== "string" && row.targets?.[0];
    const e = at && !all.some((r) => r.id === at) && document.getElementById(at);
    return e && body.contains(e) ? [e] : [];
  }
  // a tfa row is drawn by the lens on its clause, not as a card
  const addressed = (r) => typeof r.text !== "string" && layerOf(r) !== "tfa" && !isGroup(r) && anchorsOf(r.id).length > 0;
  /**
   * A fact whose row is gone (an unbundled parts row, a deleted span):
   * no text, its first target shaped as a row id (lit's generated ids
   * carry a colon, a ledger is L-..., a file has a slash, an address is
   * b1s2c3) that names no row and no place on the page. It gets a lost
   * card, as a span not found does, so it can be moved or deleted
   * rather than sit unseen until lit refuses it. Worked out once per
   * set of rows.
   */
  const ROWLIKE = /^(?!L-[A-Z0-9]+$)(?![^/\s]*b[1-9]\d*(?:s[1-9]\d*(?:c[1-9]\d*)?)?$)[^:/\s]+$/;
  let orphans = { of: null, ids: new Set() };
  const orphan = (r) => {
    if (orphans.of !== all) {
      const ids = new Set(all.map((x) => x.id));
      orphans = { of: all, ids: new Set(all.filter((x) => typeof x.text !== "string" && !RELATIONS.has(x.labels?.[0] ?? "")
        && !SETKINDS.has(x.labels?.[0] ?? "") && !isGroup(x) && layerOf(x) !== "tfa" && typeof x.targets?.[0] === "string"
        && ROWLIKE.test(x.targets[0]) && !ids.has(x.targets[0]) && !place(x.targets[0])).map((x) => x.id)) };
    }
    return orphans.ids.has(r.id);
  };

  /** Every row, the sidecar's first, each marked mine when it is local. */
  const rows = () => [...sidecar, ...local().map((r) => ({ ...r, mine: true }))];
  let all = [], state = {};

  /** A row's layer, read as lit's facts.layer reads it: never written down. */
  function layerOf(r) {
    const k = r.labels?.[0] ?? "";
    if (typeof r.text === "string" || k === "parts") return "span";
    if (k === "supports" || k === "attacks") return "argument";
    if (k === "resumes" || k.startsWith("tfa/")) return "tfa";
    if (k === "coref") return "coref";
    if (isGroup(r)) return "group";
    if (RELATIONS.has(k)) return "relation";
    const up = all.find((x) => x.id === r.targets?.[0]);
    return up && typeof up.text !== "string" && up.labels?.[0] !== "parts" ? "thread" : "fact";
  }
  const sheetOf = (r) => (r.labels?.[0] === "resumes" ? "resumes" : layerOf(r));
  const shows = (r) => !offLayers().has(sheetOf(r));

  /** The labels a span is filtered by: its own and those of the facts about it, in the layers shown. */
  function labelsOf(row) {
    const got = new Set(row.labels ?? []);
    const walk = (id) => { for (const r of all.filter((x) => typeof x.text !== "string" && x.labels?.[0] !== "parts" && !isGroup(x) && x.targets?.[0] === id && shows(x))) {
      for (const l of r.labels ?? []) got.add(l); walk(r.id); } };
    for (const id of bundleOf(row.id) ? treeOf(bundleOf(row.id)).filter(bundleOf) : [row.id]) walk(id);   // a bundle in it is the whole's too
    for (const g of groupsOf(row.id)) for (const l of g.labels) got.add(l);   // a group names its members, each of them
    return got.size ? got : new Set([NONE]);
  }
  const passes = (row) => { const off = [...hidden()]; return [...labelsOf(row)].some((l) => !off.some((h) => under(l, h))); };

  const css = getComputedStyle(document.documentElement);
  /** A row's colour: its label's (the kind its card shows), else the weave's for a row of the sidecar or of this browser. */
  const tone = (row) => { const k = row && kindOfCard(wholeOf(row.id) ?? row);
    return k ? colourOf(k) : css.getPropertyValue(!row || row.mine ? "--fpl-mine" : "--fpl-vers").trim(); };
  /**
   * Colour the marks as the boards do: the spans over a stretch of text
   * are its layers, the longest outermost. The text is washed in the
   * innermost span's colour, 20% and 12% more for each layer around it,
   * at most 70% and never so much that the text falls under 4.5:1 on it;
   * under it one 2px line per layer, the outermost lowest, thinner past
   * three layers so the stack stays clear of the letters. A mark's
   * marks around it in the DOM are the layers of its own text, in
   * whatever order they were wrapped.
   */
  function paint(size) {
    const bg = getComputedStyle(document.body).backgroundColor;
    const ground = /^rgba\(.*, 0\)$/.test(bg) ? "#ffffff" : bg;   // a transparent body is the white canvas
    const tones = {};
    for (const m of body.querySelectorAll("mark.fact")) {
      const ids = [];
      for (let e = m; e; e = e.parentElement?.closest("mark.fact")) if (!ids.includes(e.dataset.id)) ids.push(e.dataset.id);
      ids.sort((a, b) => (size[b] ?? 0) - (size[a] ?? 0));
      const cs = ids.map((id) => tones[id] ??= tone(all.find((r) => r.id === id)));
      const lc = cs.at(-1), d = cs.length - 1;
      let p = Math.min(0.7, 0.2 + 0.12 * d);
      const fg = getComputedStyle(m).color;   // a link or code in a span has its own
      while (p > 0 && contrast(fg, mix(lc, p, ground)) < 4.5) p -= 0.02;
      m.style.setProperty("--lc", lc);
      m.style.setProperty("--wash", mix(lc, Math.max(0, p), ground));
      const t = Math.min(2, 6 / cs.length);   // never taller than three lines: a deeper stack would cross the letters
      m.style.setProperty("--u", cs.map((c, i) => `inset 0 -${+(t * (i + 1)).toFixed(2)}px 0 ${c}`).join(", "));
    }
  }

  /** Remove the marks, draw every row the stand and the filter allow, and lay the margin out. */
  function draw() {
    for (const m of body.querySelectorAll("mark.fact")) m.replaceWith(...m.childNodes);
    body.normalize();
    all = rows();
    if (asked) try { found = new Set(QUERY.query(all, asked)); } catch { found = null; }   // an edit changes what the query finds
    state = {};
    const size = {};
    for (const row of all) {
      if (typeof row.text !== "string" || !row.text.trim()) continue;
      const ix = shown(), at = find(ix, row);
      state[row.id] = typeof at === "string" ? at : "vers";
      const p = wholeOf(row.id);   // a piece shows when its whole does
      if (typeof at !== "string" && mode() !== "lezen" && (p ? passes(p) : passes(row))) { wrap(ix, at[0], at[1], row); size[row.id] = at[1] - at[0]; }
    }
    paint(size);
    for (const row of all) if (addressed(row)) state[row.id] = "vers";
    for (const p of all.filter((r) => r.labels?.[0] === "parts"))   // a whole is found only when every piece is
      state[p.id] = leavesOf(p).every((t) => state[t] === "vers") ? "vers" : "stale";
    layout();
  }

  /* ---- the bar: the stands, the search, Weergave and a menu, in one place ---- */

  /** The bar's icons, one stroke on a 16-unit grid (the canvas boards' set). */
  const ICONS = {
    graph: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="3.5" r="1.8"/><circle cx="3.5" cy="12.5" r="1.8"/><circle cx="12.5" cy="12.5" r="1.8"/><path d="M7.2 5.1 4.4 10.9M8.8 5.1l2.8 5.8M5.3 12.5h5.4"/></g>',
    more: '<g fill="currentColor"><circle cx="3.5" cy="8" r="1.3"/><circle cx="8" cy="8" r="1.3"/><circle cx="12.5" cy="8" r="1.3"/></g>',
    search: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14"/></g>',
    filter: '<path fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" d="M2.5 3h11L9.5 8v4.5l-3 1.5V8z"/>',
    chevron: '<path fill="none" stroke="currentColor" stroke-width="1.6" d="m4 6 4 4 4-4"/>',
    deeper: '<path fill="none" stroke="currentColor" stroke-width="1.6" d="m6 4 4 4-4 4"/>',
    why: '<g fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="6"/><path d="M6.3 6.4a1.8 1.8 0 1 1 2.5 1.6c-.5.2-.8.6-.8 1.1v.4"/></g><circle cx="8" cy="11.6" r=".8" fill="currentColor"/>',
    name: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="5.5" r="2.5"/><path d="M3 13.5a5 5 0 0 1 10 0"/></g>',
    import: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M8 2v8M5 7l3 3 3-3M3 11v2.5h10V11"/>',
    export: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M8 10V2M5 5l3-3 3 3M3 11v2.5h10V11"/>',
    log: '<g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3.5" y="2" width="9" height="12" rx="1"/><path d="M6 5.5h4M6 8h4M6 10.5h2.5"/></g>',
    fold: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M2 8h12M8 1.5v4M6 3.5l2 2 2-2M8 14.5v-4M6 12.5l2-2 2 2"/>',
    context: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 4h10M3 8h10M3 12h6"/>',
    keys: '<g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="4" width="13" height="8" rx="1.5"/><path d="M4 7h1M7 7h1M10 7h1M5 9.5h6"/></g>',
    wipe: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 9h5.6l.7-9"/>',
    select: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6 2.5h4M6 13.5h4M8 2.5v11"/>',
    knob: '<circle cx="8" cy="8" r="3.5" style="fill: var(--fpl-mine)"/>',
    clear: '<path fill="none" stroke="currentColor" stroke-width="1.8"'
      + ' d="m4 4 8 8M12 4l-8 8"/>',
    shift: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="m5 6 3-3 3 3M5 10l3 3 3-3"/>',
    reply: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6.5 4 2.5 8l4 4M2.5 8H10a3.5 3.5 0 0 1 3.5 3.5V13"/>',
    tree: '<g fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3.5 2v9.5h3M3.5 5.5h3"/><rect x="7.5" y="3.5" width="6" height="4" rx="1"/><rect x="7.5" y="9.5" width="6" height="4" rx="1"/></g>',
    tray: '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" d="M2.5 9.5 4 3.5h8l1.5 6v3h-11zM2.5 9.5h3.5l.8 1.5h2.4l.8-1.5h3.5"/>',
    link: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M6.5 9.5l3-3M7 4.5l1-1a2.8 2.8 0 0 1 4 4l-1 1M9 11.5l-1 1a2.8 2.8 0 0 1-4-4l1-1"/>',
    supports: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.5"/><path d="M8 5.5v5M5.5 8h5"/></g>',
    attacks: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="5.5"/><path d="M5.5 8h5"/></g>',
    same: '<g fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="6" cy="8" r="4"/><circle cx="10" cy="8" r="4"/></g>',
    cites: '<path fill="none" stroke="currentColor" stroke-width="1.5" d="M3 12V9a3.5 3.5 0 0 1 3.5-3.5M9 12V9a3.5 3.5 0 0 1 3.5-3.5"/>',
    margin: '<g fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 3.5h6M2 6.5h6M2 9.5h6M2 12.5h4"/><rect x="10" y="3" width="4" height="5" rx="1"/></g>',
    group: '<g fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1.5" y="2.5" width="13" height="11" rx="2" stroke-dasharray="2.5 1.5"/>'
      + '<path d="M4.5 6h7M4.5 10h4.5"/></g>',
    check: '<path fill="none" stroke="currentColor" stroke-width="1.8" d="m3 8.5 3 3 7-7.5"/>',
    // the other relations' signs, each its own shape (feedback 24)
    contradicts: '<g fill="none" stroke="currentColor" stroke-width="1.5">'
      + '<circle cx="8" cy="8" r="5.5"/><path d="M4.2 11.8 11.8 4.2"/></g>',
    because: '<g fill="currentColor"><circle cx="3.8" cy="5" r="1.7"/>'
      + '<circle cx="12.2" cy="5" r="1.7"/>'
      + '<circle cx="8" cy="11.5" r="1.7"/></g>',
    supersedes: '<path fill="none" stroke="currentColor" stroke-width="1.6"'
      + ' d="m3 4 4 4-4 4M9 4l4 4-4 4"/>',
    relates: '<path fill="none" stroke="currentColor" stroke-width="1.5"'
      + ' d="M8 2.5 13.5 8 8 13.5 2.5 8z"/>',
    // a graph card's kind, beside its word: a span a square, a fact a dot
    kspan: '<rect x="3" y="3" width="10" height="10" rx="2"'
      + ' fill="currentColor"/>',
    knote: '<circle cx="8" cy="8" r="5" fill="currentColor"/>',
    kbesluit: '<path fill="none" stroke="currentColor" stroke-width="1.6"'
      + ' stroke-linejoin="round" d="M4 2.5h8v11L8 10.5l-4 3z"/>',
    kweigering: '<path fill="none" stroke="currentColor" stroke-width="1.6"'
      + ' stroke-linejoin="round"'
      + ' d="M5.7 2.5h4.6l3.2 3.2v4.6l-3.2 3.2H5.7l-3.2-3.2V5.7z"/>',
    ktest: '<path fill="none" stroke="currentColor" stroke-width="1.6"'
      + ' stroke-linejoin="round" d="M5.5 2.5h5M6.8 2.5v4L3 13.5h10'
      + 'L9.2 6.5v-4"/>',
    kchunk: '<path fill="none" stroke="currentColor" stroke-width="1.6"'
      + ' d="M6 3.5 2 8l4 4.5M10 3.5l4 4.5-4 4.5"/>',
    kbestand: '<path fill="none" stroke="currentColor" stroke-width="1.5"'
      + ' stroke-linejoin="round" d="M3.5 1.5h6l3 3v10h-9zM9.5 1.5v3h3"/>',
    kplek: '<path fill="none" stroke="currentColor" stroke-width="1.5"'
      + ' d="M6.5 2 5 14M11 2 9.5 14M2.5 5.5h11M2 10.5h11"/>',
    kelders: '<circle cx="8" cy="8" r="5" fill="none" stroke="currentColor"'
      + ' stroke-width="1.5" stroke-dasharray="2.2 1.8"/>',
  };
  const ico = (name) => {
    const s = el("span", { className: "fpl-ico" });
    s.ariaHidden = "true";
    s.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16">${ICONS[name]}</svg>`;
    return s;
  };
  /** A button of the bar: an icon, and a name that a narrow bar keeps for the screen reader only. */
  const tool = (name, text, onclick) => {
    const b = button("", onclick, "fpl-tool");
    b.append(ico(name), el("span", { className: "fpl-name" }, text));
    return b;
  };

  const STANDS = { lezen: "Lezen", spans: "Spans", kantlijn: "Kantlijn" };
  const stand = (m) => { if (m !== "kantlijn") disarm(); mode(m); draw(); };
  const tabs = el("div", { className: "fpl-tabs", role: "tablist", ariaLabel: "Stand" },
    ...MODES.map((m) => Object.assign(button(STANDS[m], () => stand(m), "fpl-tab"), { role: "tab" })));
  const picker = el("select", { className: "fpl-stand", ariaLabel: "Stand", onchange: () => stand(picker.value) },
    ...MODES.map((m) => el("option", { value: m }, STANDS[m])));
  /*
   * The Weergave menu (board V4b; feedback 18): what stands beside the
   * text, one of three. Kantlijn is the page with its margin, the plane
   * closed (not the stand of that name: a stand says what the text
   * shows, a view what stands beside it); Graph and Boom open the plane
   * in that view, or turn it in place. Canvas, the boards' fourth, is
   * left out until it is built: the list holds what works. The button
   * names the view while the plane is open ("Weergave: Boom"); folded,
   * it is the view's icon.
   */
  const VIEWS = [["kantlijn", "Kaarten", "margin"], ["graph", "Graph", "graph"], ["boom", "Boom", "tree"]];
  const viewOf = () => plane?.view ?? "kantlijn";
  /** A page with no row and no chunk has nothing for the plane: its Graph and Boom are off (QA, block 4: a blank plane). */
  const bare = () => !all.length && !code?.nodes?.length;
  const view = (v) => { shut(); if (v === "kantlijn") plane?.close(); else if (!bare()) graph(null, v); };
  /** The tree in the plane, or closed: the key b. */
  const boom = () => { shut(); if (plane?.view === "boom") plane.close(); else if (!bare()) graph(null, "boom"); };
  const viewBtn = button("", () => {
    flip(views, viewBtn, fillViews);
    views.querySelector('[aria-checked="true"]')?.focus({ preventScroll: true });
  }, "fpl-tool fpl-view");
  const moreBtn = tool("more", "Meer", () => flip(menu, moreBtn, fillMenu));
  const filterBtn = tool("filter", "Filter: labels en lagen", () => flip(panel, filterBtn, fillChips));
  filterBtn.title = "Filter: lagen en labels";
  moreBtn.classList.add("fpl-icon", "fpl-more"); filterBtn.classList.add("fpl-icon", "fpl-filter-btn");
  for (const b of [moreBtn, filterBtn, viewBtn]) { b.ariaHasPopup = "true"; b.ariaExpanded = "false"; }
  const field = el("input", { className: "fpl-query", placeholder: "Zoek of filter, bv. label:claim", ariaLabel: "Zoek of filter",
    autocomplete: "off", spellcheck: false });
  // a query asked (board H): the field is lit, its / gives way to an x
  const clear = el("button", { type: "button", className: "fpl-x",
    ariaLabel: "Wis het filter", title: "Wis het filter",
    onclick: () => { field.value = ""; ask(); field.focus(); } }, ico("clear"));
  const search = el("div", { className: "fpl-search" },
    ico("search"), field, el("kbd", {}, "/"), clear);
  // the counts are for a screen reader only (QA, block 4: no count line on screen); lost rows are their strips, a filter
  // lights the funnel, a bad query reddens the field and says why under the mouse
  const count = el("p", { className: "fpl-count fpl-sr", role: "status" });
  const row = el("div", { className: "fpl-row" }, tabs, el("span", { className: "fpl-picker" }, picker, ico("chevron")), viewBtn, moreBtn);
  const bar = el("div", { className: "fpl-annot-ui fpl-topbar", role: "region", ariaLabel: "Kantlijn" }, row, search, count);
  const menu = el("div", { className: "fpl-annot-ui fpl-menu", hidden: true });
  const views = el("div", { className: "fpl-annot-ui fpl-menu fpl-views", hidden: true, role: "menu", ariaLabel: "Weergave" });
  /** The button: Weergave, or Weergave: and the view while the plane is open; the view's icon for the folded bar. */
  function drawView() {
    const v = viewOf(), [, name, icon] = VIEWS.find(([k]) => k === v);
    viewBtn.replaceChildren(ico(icon), el("span", { className: "fpl-name" },
      ...v === "kantlijn" ? ["Weergave"] : [el("span", { className: "fpl-vl" }, "Weergave: "), name]), ico("chevron"));
    if (!views.hidden) fillViews();
  }
  /** The menu: the three views as radio items, a check on the one shown; ↑ ↓ move, Enter chooses. */
  function fillViews() {
    const v = viewOf(), was = [...views.children].indexOf(document.activeElement);   // a redraw keeps the focus where it was
    views.replaceChildren(...VIEWS.map(([k, name]) => {
      const b = button("", () => view(k), "fpl-item");
      b.role = "menuitemradio"; b.ariaChecked = String(k === v);
      if (k !== "kantlijn" && bare()) { b.disabled = true; b.title = "Nog niets op deze pagina"; }
      b.append(k === v ? ico("check") : el("span", { className: "fpl-ico" }), name);
      if (k === "boom") b.append(el("kbd", {}, "b"));
      return b;
    }));
    views.children[was]?.focus({ preventScroll: true });
  }
  views.onkeydown = (e) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const items = [...views.children], i = items.indexOf(document.activeElement);
    items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length]?.focus();
  };
  const chips = el("div", { className: "fpl-filters" });
  const panel = el("div", { className: "fpl-annot-ui fpl-menu fpl-panel", hidden: true, role: "group", ariaLabel: "Filter" }, chips);
  const file = el("input", { type: "file", accept: ".json", hidden: true });
  file.onchange = () => { file.files[0]?.text().then(merge); file.value = ""; };
  bar.append(file);
  let bad = "";   // why the query in the field does not parse

  /** Run the query in the field; a query in Lezen shows the spans, since Lezen draws none. */
  const ask = () => {
    const was = bands.length > 0 && folded(runsNear(context));   // to the spans
    asked = field.value.replace(/^ +| +$/g, "");   // only U+0020 apart, as the parser
    try { found = asked ? new Set(QUERY.query(all, asked)) : null; bad = ""; }
    catch (e) { found = null; bad = e.message; }
    field.classList.toggle("is-bad", !!bad);
    search.classList.toggle("is-on", !!asked);
    field.title = bad;
    if (asked && mode() === "lezen") stand("spans"); else layout();
    // folded to the spans: refold to the new ones, as a new Context does
    if (was) setBands(runsNear(context) ?? []);
  };
  /** The funnel opens the panel, in the field of the full bar as in the folded one; typing a query closes it. */
  field.oninput = () => { if (field.value && bar.classList.contains("is-full") && !panel.hidden) shut(); };
  field.onkeydown = (e) => {
    e.stopPropagation();   // j, k, a, 1-4 and Esc belong to the page, not while typing a query
    if (e.key === "Enter") ask();
    if (e.key === "Escape") { if (field.value) { field.value = ""; ask(); } else { shut(); field.blur(); } }
  };

  /**
   * Where the bar goes, measured each layout. Where Quarto shows its top
   * bar (a narrow window) the bar docks in it, left of the site's search,
   * folded to a stand picker and three icons, and the search field and
   * the counts move into the filter panel. Where the margin has 320px
   * (from about 1380px wide), the bar is fixed above it, as wide as the
   * margin. Between the two it is the folded bar, fixed at the top right.
   */
  const nav = document.querySelector(".quarto-secondary-nav .container-fluid");
  function dock() {
    const over = !!plane?.beside;   // the bar heads the plane (board V2b), as wide as it
    const top = !over && !!nav && nav.offsetHeight > 0, room = over ? innerWidth - plane.x : wide() ? reserve() : 0;
    const full = !top && room >= 320;
    bar.classList.toggle("is-full", full);
    bar.classList.toggle("is-docked", top);
    bar.classList.toggle("is-plane", over);
    bar.style.left = full ? `${over ? plane.x : rail()}px` : "";
    bar.style.width = full ? `${room}px` : "";
    if (top) { if (bar.parentElement !== nav) nav.insertBefore(bar, nav.querySelector(".quarto-search-button")); }
    else if (bar.parentElement !== document.body) document.body.append(bar);
    if (bar.dataset.form !== String(full)) {   // the folded bar keeps the search in its panel
      bar.dataset.form = full;
      if (full) { search.append(filterBtn); bar.insertBefore(search, file); bar.insertBefore(count, file); }
      else { row.insertBefore(filterBtn, viewBtn); panel.prepend(search, count); }
    }
    if (!menu.hidden) hang(menu, moreBtn);
    if (!views.hidden) hang(views, viewBtn);
    if (!panel.hidden) hang(panel, full ? search : filterBtn);
  }

  /** The bar's state: which stand, the counts, the filter's mark; the open panel's chips. */
  function drawBar() {
    const cur = mode();
    bar.dataset.stand = cur;   // the search's / shows in Kantlijn only
    for (const [i, t] of [...tabs.children].entries()) { t.ariaSelected = String(MODES[i] === cur); t.classList.toggle("is-on", MODES[i] === cur); }
    picker.value = cur;
    const spans = all.filter((r) => typeof r.text === "string" || addressed(r));
    const lost = spans.filter((r) => state[r.id] !== "vers").length + all.filter(orphan).length, mine = local().length;
    const head = all.length
      ? `${spans.length} spans · ${all.length - spans.length} relaties`
      : "Nog geen spans op deze pagina";
    const line = el("p", {}, head,
      lost ? el("span", { className: "fpl-lost" }, ` · ${lost} kwijt`) : null,
      mine ? el("span", { className: "fpl-mine" }, ` · ${mine} van jou`) : null,
      bad ? el("span", { className: "fpl-bad" }, ` · ${bad}`) : found ? ` · ${found.size} gevonden` : null,
      hidden().size + offLayers().size
        ? el("span", { className: "fpl-mine" }, " · filter aan") : null);
    count.title = line.textContent;
    // folded to the spans (board H): how many spans the fold keeps, of all
    if (bands.length && folded(runsNear(context))) {
      const kept = new Set([...body.querySelectorAll("mark.fact")]
        .filter((m) => !m.matches(".fpl-faded")).map((m) => m.dataset.id));
      const k = spans.filter((r) => kept.has(r.id)).length;
      count.replaceChildren(`${k} van ${spans.length} spans · `,
        el("b", {}, "ingevouwen tot de spans"), `, context ${context}`);
    } else count.replaceChildren(...line.childNodes);
    filterBtn.classList.toggle("is-on", hidden().size + offLayers().size > 0);
    drawView();
    if (!panel.hidden) fillChips(); else fillSheets();
    dock();
  }

  /** Open one popover under its button, or close it if it was open; one at a time. focus false leaves the focus where it is. */
  function flip(pop, btn, fill, focus = true) {
    const was = !pop.hidden;
    shut();
    if (was) return;
    fill();
    pop.hidden = false;
    btn.ariaExpanded = "true";
    btn.classList.add("is-open");
    hang(pop, pop === panel && bar.classList.contains("is-full") ? search : btn);
    if (focus) pop.querySelector("button:not(:disabled):not(.fpl-why), [tabindex='0']")?.focus({ preventScroll: true });   // not a (?)
  }
  /** A popover hangs under what opened it, right edges flush, inside the window. */
  function hang(pop, at) {
    const r = at.getBoundingClientRect();
    pop.style.top = `${Math.max(8, r.bottom + 6)}px`;   // a docked bar may have scrolled away with Quarto's header
    pop.style.right = `${Math.max(8, innerWidth - r.right)}px`;
    pop.style.width = at === search ? `${r.width}px` : "";
  }
  /** Close the menu, the filter panel and a card's menu. */
  function shut() {
    if (link?.open) { link = null; drawAim(); hot(null); toast("Niet verbonden"); }   // the chooser closed unanswered
    for (const [pop, btn] of [[menu, moreBtn], [panel, filterBtn], [views, viewBtn]]) { pop.hidden = true; btn.ariaExpanded = "false"; btn.classList.remove("is-open"); }
    cardMenu.hidden = true;
    if (menuOf) for (const b of margin.querySelectorAll(".fpl-card-more")) b.ariaExpanded = "false";
    menuOf = null;
  }
  document.addEventListener("pointerdown", (ev) => {
    const t = ev.target;
    if (link?.open && t.closest?.(".fpl-knob")) { link = null; drawAim(); }   // a new drag replaces the question, quietly
    if (!t.closest?.(".fpl-menu, .fpl-card-more") && !moreBtn.contains(t) && !filterBtn.contains(t) && !viewBtn.contains(t) && t !== field) shut();
  }, true);
  /** A click outside every card, menu and panel lets the open card close; not while a new fact is written. */
  document.addEventListener("click", (ev) => {
    if (!openId || ev.target.closest?.(".fpl-card, .fpl-menu, .fpl-pop, .fpl-graph, .fpl-toast, .fpl-topbar")) return;
    openId = null;
    if (!editing) layout();
  });

  /*
   * The filter panel (board V4a): the layers as six buttons, then the
   * labels as a field over their scopes. A layer button's click turns its
   * layer on or off, Shift-click (or Shift with its key) shows it alone,
   * the rest of the page dimmed, and again shows all; the keys 1-4 do the
   * same from anywhere outside Lezen. The field narrows the list to the
   * scopes under what it holds: up and down choose, right goes a level
   * deeper ("slop/"), left back up, Enter or a click strikes or restores
   * the label (and all under it), Shift shows that label alone. A label
   * of MEANING has a (?) that says it. The field has no key of its own:
   * one / per screen, the search's.
   */
  const sheets = el("div", { className: "fpl-sheets", role: "group", ariaLabel: "Lagen" });
  // the spans and the threads are no layer to read by: a row of their own, under Ook (board V4a; QA: one list, one kind)
  const also = el("div", { className: "fpl-sheets fpl-also", role: "group", ariaLabel: "Ook" });
  const LAYERWHY = "Argument: steunt en valt aan, als boom op de kaart. Coref: een ketennummer bij elk lid. "
    + "Topic-focus: een waas per bijzin, t, c of f. Progressie: bogen in de linker goot naar wat een bijzin opneemt. "
    + "Shift-klik of Shift+1-4: alleen die laag.";
  const labelHead = el("p", { className: "fpl-panel-head" });
  const labelField = el("input", { className: "fpl-labelq", placeholder: "Typ een label, → een laag dieper", ariaLabel: "Label zoeken",
    autocomplete: "off", spellcheck: false, role: "combobox", ariaExpanded: "true", ariaAutoComplete: "list" });
  const labelList = el("ul", { className: "fpl-scopes", role: "listbox", id: "fpl-scopes", ariaLabel: "Labels",
    title: "Klik verbergt een label en alles eronder; Shift-klik toont alleen dat label" });
  labelField.setAttribute("aria-controls", labelList.id);
  chips.append(el("p", { className: "fpl-panel-head" }, "Lagen", el("button", { type: "button", className: "fpl-why", title: LAYERWHY,
    ariaLabel: `Wat zijn de lagen? ${LAYERWHY}`, onclick: () => toast(LAYERWHY) }, ico("why"))), sheets, also, labelHead, labelField, labelList);
  let lit = 0;   // the chosen row of the label list

  /** A layer on or off; shift: alone, the other three and the threads off (an argument keeps its spans), or, alone already, all back. */
  function toggleLayer(k, shift) {
    const o = offLayers();
    if (!shift || !FOUR.includes(k)) o.has(k) ? o.delete(k) : o.add(k);
    else if (alone() === k) o.clear();
    else { o.clear(); for (const [x] of SHEETS) if (x !== k && !(k === "argument" && x === "span")) o.add(x); }
    offLayers(o);
    draw();
  }

  /** Each scope of the labels on spans and addressed rows, with how many of those rows carry it. */
  function scopeTally() {
    const n = new Map();
    for (const r of all.filter((r) => typeof r.text === "string" || addressed(r)))
      for (const s of new Set([...labelsOf(r)].flatMap(scopes))) n.set(s, (n.get(s) ?? 0) + 1);
    return n;
  }

  /** Strike a label, or bring it back; alone: strike every other scope beside its path, or, so already, none. */
  function strike(l, solo) {
    const o = hidden();
    if (solo) {
      const rest = [...scopeTally().keys()].filter((x) => !under(x, l) && !under(l, x)
        && (!x.includes("/") || under(l, x.slice(0, x.lastIndexOf("/")))));
      hidden(new Set(rest.length === o.size && rest.every((x) => o.has(x)) ? [] : rest));
      draw();
      return;
    }
    const above = [...o].find((h) => h !== l && under(l, h));
    if (above) { toast(`Zet eerst ${above} aan`); return; }   // struck by its scope: the scope decides
    o.has(l) ? o.delete(l) : o.add(l);
    hidden(o);
    draw();
  }

  /** The label list for what the field holds: the scopes one level under its last "/", the typed rest in their name. */
  function fillLabels() {
    const v = labelField.value.toLowerCase(), cut = v.lastIndexOf("/"), at = v.slice(0, cut + 1), typed = v.slice(cut + 1);
    const n = scopeTally(), off = hidden(), depth = at.split("/").length;
    const name = (l) => (VERB[l] ?? "") + " " + l.slice(l.lastIndexOf("/") + 1).toLowerCase();
    let here = [...n.keys()].filter((l) => l.split("/").length === depth && l.toLowerCase().startsWith(at) && name(l).includes(typed));
    if (!here.length && typed) here = [...n.keys()].filter((l) => l.toLowerCase().includes(typed));   // nothing on this level: anywhere
    here.sort((a, b) => (a === NONE) - (b === NONE) || n.get(b) - n.get(a) || a.localeCompare(b));
    lit = Math.max(0, Math.min(lit, here.length - 1));
    labelList.replaceChildren(...here.map((l, i) => {
      const deeper = [...n.keys()].some((x) => x.startsWith(l + "/")), struck = [...off].some((h) => under(l, h));
      const cut = l.lastIndexOf("/") + 1, why = MEANING[l];
      const li = el("li", { id: `fpl-scope-${i}`, role: "option", className: struck ? "is-off" : "", ariaSelected: String(i === lit) },
        l === NONE ? null : el("span", { className: "fpl-sq", style: `--lc: ${colourOf(l)}` }),
        el("span", { className: "fpl-scope" }, cut && !at ? el("small", {}, l.slice(0, cut)) : null, VERB[l] ?? l.slice(cut)),
        el("span", { className: "fpl-ct" }, String(n.get(l))),
        why ? el("button", { type: "button", className: "fpl-why", title: why, ariaLabel: `Wat is ${l}? ${why}`,
          onclick: (e) => { e.stopPropagation(); toast(`${l}: ${why}`); } }, ico("why")) : null,
        deeper ? el("button", { type: "button", className: "fpl-deeper", ariaLabel: `Onder ${l}`,
          onclick: (e) => { e.stopPropagation(); descend(l); } }, ico("deeper")) : null);
      li.dataset.label = l;
      li.onclick = (e) => strike(l, e.shiftKey);
      return li;
    }));
    if (!here.length) labelList.append(el("li", { className: "fpl-panel-none" }, n.size ? "Geen label zo" : "Nog geen labels op deze pagina"));
    labelField.setAttribute("aria-activedescendant", here.length ? `fpl-scope-${lit}` : "");
  }
  const descend = (l) => { labelField.value = l + "/"; lit = 0; fillLabels(); labelField.focus(); };
  labelField.oninput = () => { lit = 0; fillLabels(); };
  labelField.onkeydown = (e) => {
    e.stopPropagation();   // j, k, 1-4 and / belong to the page, not while typing a label
    const items = [...labelList.querySelectorAll("[data-label]")], cur = items[lit]?.dataset.label, v = labelField.value;
    const end = labelField.selectionStart === v.length;
    if ((e.key === "ArrowDown" || e.key === "ArrowUp") && items.length) {
      e.preventDefault();
      lit = (lit + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      fillLabels();
    } else if (e.key === "ArrowRight" && end && cur && items[lit].querySelector(".fpl-deeper")) { e.preventDefault(); descend(cur); }
    else if (e.key === "ArrowLeft" && v.endsWith("/")) {   // back up: the scope we came from chosen
      e.preventDefault();
      const from = v.slice(0, -1), up = from.slice(0, from.lastIndexOf("/") + 1);
      labelField.value = up;
      fillLabels();
      lit = Math.max(0, [...labelList.querySelectorAll("[data-label]")].findIndex((x) => x.dataset.label.toLowerCase() === from));
      fillLabels();
    } else if (e.key === "Enter" && cur) { e.preventDefault(); strike(cur, e.shiftKey); }
    else if (e.key === "Escape") { e.preventDefault(); if (v) { labelField.value = ""; lit = 0; fillLabels(); } else { shut(); field.focus(); } }
  };

  /** The layer buttons, pressed as they stand; drawn with the bar, so they never lag behind a key. */
  function fillSheets() {
    const off = offLayers(), was = chips.contains(document.activeElement) ? document.activeElement.dataset.sheet : null;
    const swatch = { argument: ["line", "supports"], coref: ["sq", "coref"], tfa: ["sq", "tfa"], resumes: ["line", "resumes"] };
    const make = ([k, name]) => {
      const [form, c] = swatch[k] ?? [], i = FOUR.indexOf(k);
      const b = el("button", { type: "button", className: "fpl-sheet", ariaPressed: String(!off.has(k)),
        title: i < 0 ? `${name} aan of uit` : `${name} · ${i + 1} · Shift-klik: alleen deze`, onclick: (e) => toggleLayer(k, e.shiftKey) },
      form ? el("span", { className: form === "sq" ? "fpl-sq" : "fpl-line", style: `--lc: ${colourOf(c)}` }) : null,
      name, i < 0 ? null : el("kbd", {}, String(i + 1)));
      b.dataset.sheet = k;
      return b;
    };
    sheets.replaceChildren(...SHEETS.slice(0, 4).map(make));
    also.replaceChildren(el("span", { className: "fpl-also-head" }, "Ook"), ...SHEETS.slice(4).map(make));
    if (was) chips.querySelector(`[data-sheet="${was}"]`)?.focus();
  }
  /** Fill the panel: the layer buttons and the label list for the field. */
  function fillChips() {
    fillSheets();
    labelHead.replaceChildren("Labels", ...hidden().size ? [button("alles aan", () => { hidden(new Set()); draw(); }, "fpl-link")] : []);
    fillLabels();
  }

  /** The menu under ⋯; ask is "export" after an export (the lit command shows), "wipe" while wiping asks. */
  function fillMenu(ask) {
    const mine = local().length, rows = mine === 1 ? "1 rij" : `${mine} rijen`;
    const entry = (name, text, onclick, after, cls = "") => {
      const b = button("", onclick, "fpl-item " + cls);
      b.append(ico(name), text, ...after ? [after] : []);
      return b;
    };
    const none = (b) => { b.disabled = true; return b; };
    const name = el("input", { value: by(), placeholder: "jij", onchange: (ev) => by(ev.target.value.trim()) });
    const ctx = el("span", { className: "fpl-ctx", role: "group", ariaLabel: "Context rond elke span, in blokken" },
      ...[0, 1, 2, 3].map((n) => Object.assign(button(String(n), () => { setContext(n); fillMenu(); }), { ariaPressed: String(n === context) })));
    // what an item would act on, or why it cannot, under the mouse: a menu holds no status words (QA, block 4)
    const exp = Object.assign(entry("export", "Exporteer rijen", () => { exportRows(); fillMenu("export"); }), { title: mine ? `${rows} van jou` : "Nog geen rijen van jou" });
    const wipe = Object.assign(entry("wipe", "Wis mijn rijen op deze pagina…", () => fillMenu("wipe"), null, "fpl-danger"), { title: mine ? `${rows} van jou` : "Nog geen rijen van jou" });
    menu.classList.remove("fpl-keysheet");
    menu.replaceChildren(...[
      el("label", { className: "fpl-item" }, ico("name"), "Naam", name),
      el("hr"),
      entry("import", "Importeer rijen…", () => { shut(); file.click(); }),
      mine ? exp : none(exp),
      ask === "export" ? el("p", { className: "fpl-cmd" }, "Dan, vanuit 01-bootstrap/: ",
        el("code", {}, `lit facts --import ${stem}.annot.json --item ${item}=${item}@${commit}`)) : null,
      Object.assign(none(entry("log", "Exporteer logboek", null)), { title: "Komt nog" }),
      el("hr"),
      entry("fold", "Vouw tot de spans", () => { shut(); squeeze(); }),
      el("div", { className: "fpl-item" }, ico("context"), "Context", ctx),
      el("hr"),
      entry("keys", "Sneltoetsen", () => keysheet(), el("kbd", {}, "?")),
      ask === "wipe"
        ? el("div", { className: "fpl-item fpl-confirm" }, `${rows} van jou wissen?`,
          button("Wis", () => { localStorage.removeItem(key); shut(); draw(); toast(`${rows} gewist`); }, "fpl-go fpl-danger"),
          button("Nee", () => fillMenu()))
        : mine ? wipe : none(wipe)].filter(Boolean));
  }

  /** The keys, in the menu's place: "?" or the menu's Sneltoetsen. */
  function keysheet() {
    if (menu.hidden) flip(menu, moreBtn, () => {});
    menu.classList.add("fpl-keysheet");
    const keys = [["a", "Volgende stand"], ["/", "Zoek of filter, in Kantlijn"], ["1  2  3  4", "Argument, Coref, Topic-focus, Progressie aan of uit"],
      ["Shift + 1-4", "Alleen die laag; nog eens: alles"], ["j  k", "Volgende, vorige zin"],
      ["Enter", "Een feit op de zin onder de cursor"], ["⌘↩", "Bewaar in de editor"],
      ["Shift + scroll",
        "Vouwt rond de muis in, terug opent; met een filter tot de spans"],
      ["Esc", "Sluit of breekt af; anders opent de laatste band"], ["Alt + selectie", "Een deel van een span; Enter bundelt"],
      ["b", "Boom: de groepen als betoog"], ["Alt + ↑ ↓", "Verplaats een groep in de boom, op zijn greep"],
      ["Alt + ←", "Terug na een sprong uit de graph of de boom"], ["Alt-klik", "De tfa-waarde van een bijzin"], ["Alt-Shift-klik", "Deze bijzin neemt een eerdere op"],
      ["l", "Verbind de kaart onder de muis of de focus; Tab kiest het andere eind, Enter het soort"],
      ["Shift + ← →", "Rek je span een woord, met de focus op zijn bolletje; Enter bewaart"], ["?", "Deze lijst"]];
    menu.replaceChildren(el("p", { className: "fpl-panel-head" }, "Sneltoetsen"),
      el("dl", {}, ...keys.flatMap(([k, what]) => [el("dt", {}, ...k.split(/ {2}/).map((x) => el("kbd", {}, x))), el("dd", {}, what)])));
    menu.tabIndex = -1;
    menu.focus({ preventScroll: true });
  }

  /** /: the search field, in the panel when the bar is folded; the full bar's panel waits for its funnel. */
  function seek() {
    if (!bar.classList.contains("is-full") && panel.hidden) flip(panel, filterBtn, fillChips);
    field.focus();
    field.select();
  }

  /** The margin when Kantlijn has no card yet: how to annotate, connect and fold, in three lines. */
  const hint = () => el("ul", { className: "fpl-hint" },
    ...[["select", "Selecteer tekst", " en schrijf een notitie."],
      ["knob", "Sleep het bolletje", " achter een span naar een andere span om ze te verbinden."],
      ["shift", "", ["Houd ", el("kbd", {}, "Shift"), " en scroll boven de tekst om hem in te vouwen. Terug scrollen opent."]]]
      .map(([i, b, rest]) => el("li", {}, ico(i), el("span", {}, b ? el("b", {}, b) : null, ...[rest].flat()))));

  /* ---- what a card shows: a head, its relations, a thread (board F) ---- */

  const chip = (label, cls) => {
    const [head, sub] = VERB[label] ? [VERB[label]] : label.split(/\/(.*)/);
    return el("span", { className: "fpl-chip " + cls, title: VERB[label] ? label : "" }, head, sub ? el("small", {}, "/" + sub) : null);
  };
  // a parts row names its pieces, it says nothing about the first one
  const facts = (id) => all.filter((r) => typeof r.text !== "string" && r.labels?.[0] !== "parts" && !isGroup(r) && r.targets?.[0] === id && shows(r));
  /** A row that ties its first target to others (supports, cites, coref): a line on the card, not a message. */
  const relates = (r) => (r.targets ?? []).length > 1;
  /** The first words of a text, cut at a word, with an ellipsis when cut. */
  const clip = (s, n = 40) => {
    const t = String(s ?? "").replace(/\s+/g, " ").trim();
    return t.length <= n ? t : `${t.slice(0, n).replace(/\s+\S*$/, "")}…`;
  };
  /** A relation's verb: Dutch for the labels lit knows, else the label as written. */
  const verb = (r) => VERB[r.labels?.[0]] ?? ((r.labels ?? []).join(" ") || "verbindt");
  /** Who wrote a row, when the row says so; a row without a name has no author line, never a "?". */
  const author = (r) => (typeof r.by === "string" && r.by.trim()) || null;
  /** A row's time, from createdAt: the clock today, else the day; nothing for a row without a real time. */
  const stamp = (t) => {
    if (!Number.isFinite(t) || t < 1e11) return "";
    const d = new Date(t);
    return d.toDateString() === new Date().toDateString()
      ? d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" })
      : d.toLocaleDateString("nl-NL", { day: "numeric", month: "short" });
  };

  /**
   * The page's decision ledger, <stem>.decisions.tsv beside the page
   * (columns id, topic, date, who, decision, reason), read once at load.
   * lit makes each of its rows a span L-<id> (facts.generate), so a
   * relation that ends at L-I4 ends at a decision: the card draws it as a
   * chip, its topic and the first words of the decision, and a click opens
   * the row, its reason, date and who, in the card.
   */
  let ledger = new Map();
  const readLedger = (tsv) => {
    const [head, ...rest] = String(tsv ?? "").split("\n").filter((l) => l.trim());
    const ks = head?.split("\t") ?? [];
    return new Map(rest.map((l) => { const v = l.split("\t"); return Object.fromEntries(ks.map((k, i) => [k, v[i] ?? ""])); })
      .filter((r) => r.id).map((r) => [r.id, r]));
  };
  const decision = (t) => { const m = /^L-(.+)$/.exec(t); return m ? { id: m[1], ...ledger.get(m[1]) } : null; };
  const told = new Set();   // "<card id> <decision id>": ledger rows opened in a card, kept across draws
  function decisionChip(d, owner) {
    const k = `${owner} ${d.id}`;
    const b = el("button", { type: "button", className: "fpl-decision", title: d.decision ? `Besluit ${d.id} uit de ledger` : `${d.id} staat niet in de ledger` },
      el("b", {}, d.topic || `besluit ${d.id}`), d.decision ? ` · ${clip(d.decision, 34)}` : " · niet in de ledger");
    b.ariaExpanded = String(told.has(k));
    b.onclick = (ev) => {
      ev.stopPropagation();
      if (!d.decision) { toast(`Besluit ${d.id} staat niet in ${stem}.decisions.tsv`); return; }
      told.has(k) ? told.delete(k) : told.add(k);
      openId = owner;
      layout();
    };
    return b;
  }
  /** A ledger row opened in a card: the decision whole, why, and when and by whom. */
  const ledgerRow = (d) => el("div", { className: "fpl-ledger" },
    el("p", {}, d.decision), d.reason ? el("p", { className: "fpl-why" }, d.reason) : null,
    el("p", { className: "fpl-when" }, [`besluit ${d.id}`, d.date, d.who && d.who !== "unclear" ? d.who : null].filter(Boolean).join(" · ")));

  /** What a target that is not a row is called: a chunk by its name, a test, a refusal; a row id that names nothing, "". */
  const named = (t) => {
    let v = t;
    try { v = decodeURIComponent(t); } catch { /* a stray % */ }
    const m = /^(chunk|test|refusal):(.*)$/.exec(v);
    if (m) return { chunk: `«${m[2].replace(/:\d+$/, "")}»`, test: `test ${m[2].replace(/:\d+$/, "")}`, refusal: `weigering “${m[2]}”` }[m[1]];
    return ROWLIKE.test(t) ? "" : v;
  };
  /**
   * The other end of a relation, by its text: a decision as its chip, a
   * row or a place on the page by its first words (a click folds what lies
   * between, Toon beide), anything else by its name; never a bare id.
   */
  function endOf(t, owner) {
    const d = decision(t);
    if (d) return decisionChip(d, owner);
    const r = all.find((x) => x.id === t), e = place(t);
    const said = r ? (typeof r.text === "string" ? plain(r.text) : r.note || (r.labels ?? []).join(" ")) : e?.textContent;
    const name = said ? `“${clip(said, 32)}”` : named(t);
    if (!name) return el("span", { className: "fpl-lost", title: t }, "iets dat weg is");
    if (!e) return el("span", { className: "fpl-end", title: t }, name);
    return el("button", { type: "button", className: "fpl-end", title: "Toon beide", onclick: (ev) => { ev.stopPropagation(); both(owner, t); } }, name);
  }
  /** A relation as a line: its verb and its other ends; data-fact lets a pick end at the relation itself (an undercut). */
  function relLine(r, owner) {
    const line = el("span", { className: "fpl-rel" }, el("b", {}, verb(r)), " → ", ...r.targets.slice(1).flatMap((t, i) => [i ? ", " : "", endOf(t, owner)]));
    line.dataset.fact = r.id;
    return line;
  }
  /** The ledger rows opened under some relations, in a card. */
  const ledgerRows = (rels, owner) => rels.flatMap((r) => r.targets.slice(1).map(decision))
    .filter((d) => d?.decision && told.has(`${owner} ${d.id}`)).map(ledgerRow);

  /**
   * What hangs from an id: the relations it starts, and the messages
   * about it or about those relations (a note on "contradicts L-G2" is a
   * message of the span's thread, as on board F).
   */
  function about(id) {
    const rels = [], msgs = [], seenIds = new Set([id]);
    for (const r of facts(id)) (relates(r) ? rels : msgs).push(r);
    for (const r of rels) for (const f of facts(r.id)) if (!seenIds.has(f.id)) { seenIds.add(f.id); (relates(f) ? rels : msgs).push(f); }
    return { rels, msgs };
  }
  /** The messages in a thread, all the way down. */
  function replies(id, been = new Set([id])) {
    let n = 0;
    for (const m of about(id).msgs) if (!been.has(m.id)) { been.add(m.id); n += 1 + replies(m.id, been); }
    return n;
  }
  const unfolded = new Set();   // the ids whose long thread is shown whole, kept across draws
  const LONG_THREAD = 4;        // more messages than this fold to "n reacties"

  /**
   * One message of a thread: its labels, who and when when known, its
   * text, the relations it starts, an arrow (on hover or focus) that
   * answers this message in the card's one field, and, one step in, the
   * messages about it. Deeper replies stay at that step, so a long
   * exchange does not walk off the card. A message of ours opens in the
   * editor on a click.
   */
  function msgView(r, owner, been) {
    const li = el("li", { className: `fpl-msg fpl-fact${r.mine ? " mine" : ""}` });
    li.dataset.fact = r.id;
    const who = author(r), when = stamp(r.createdAt), own = relates(r) ? [] : r.labels ?? [];
    if (who || when || own.length)
      li.append(el("div", { className: "fpl-mhead" }, ...own.map((l) => chip(l, r.mine ? "is-mine" : "is-vers")),
        who ? el("b", {}, who) : null, when ? el("span", {}, when) : null));
    const { rels, msgs } = about(r.id);
    if (relates(r)) rels.unshift(r);
    if (r.note) li.append(el("p", { className: "fpl-text" }, r.note));
    if (rels.length) li.append(el("p", { className: "fpl-meta" }, ...rels.flatMap((x, i) => [i ? " · " : "", relLine(x, owner)])), ...ledgerRows(rels, owner));
    const box = argBox(r.id);
    if (box) li.append(box);
    const to = el("button", { type: "button", className: "fpl-ib fpl-rep", ariaLabel: "Antwoord op dit bericht", title: "Antwoord op dit bericht" }, ico("reply"));
    to.onclick = (ev) => { ev.stopPropagation(); aim(li.closest(".fpl-card"), r); };
    li.append(to);
    const sub = msgs.filter((m) => !been.has(m.id));
    if (sub.length) {
      for (const m of sub) been.add(m.id);
      li.append(el("ol", { className: "fpl-msgs sub" }, ...sub.map((m) => msgView(m, owner, been))));
    }
    if (r.mine) li.onclick = (ev) => {
      if (picking || ev.target.closest("button, a, details, input, label, .fpl-msg .fpl-msg")) return;
      ev.stopPropagation();
      edit(r, null, li.getBoundingClientRect());
    };
    return li;
  }
  /** Point the card's one answer field at a message: its placeholder says whom it answers; Esc points it back at the card. */
  function aim(card, r) {
    const field = card?.querySelector(".fpl-answer input");
    if (!field) return;
    for (const m of card.querySelectorAll(".fpl-msg.is-aimed")) m.classList.remove("is-aimed");
    if (r) {
      field.dataset.to = r.id;
      field.placeholder = author(r) ? `Antwoord aan ${author(r)}…` : `Antwoord op “${clip(r.note || verb(r), 22)}”…`;
      card.querySelector(`.fpl-msg[data-fact="${CSS.escape(r.id)}"]`)?.classList.add("is-aimed");
    } else {
      field.dataset.to = card.dataset.id;
      field.placeholder = "Antwoord…";
    }
    field.focus({ preventScroll: true });
  }
  /** The card's one answer field: Enter saves a reply row to what it points at, the card stays open. */
  function answerField(id) {
    const field = el("input", { type: "text", placeholder: "Antwoord…", autocomplete: "off" });
    field.dataset.to = id;
    field.onkeydown = (e) => {
      e.stopPropagation();   // j, k, a, z, l and Esc belong to the page, not while typing
      if (e.key === "Escape") { if (field.dataset.to !== id) aim(field.closest(".fpl-card"), null); else field.blur(); return; }
      if (e.key !== "Enter" || e.isComposing) return;
      e.preventDefault();
      const note = field.value.trim();
      if (!note) { toast("Leeg antwoord: typ eerst iets"); return; }
      save({ targets: [field.dataset.to] }, { note, labels: [] });
      openId = id;
      draw();
      margin.querySelector(`.fpl-card[data-id="${CSS.escape(id)}"] .fpl-answer input`)?.focus({ preventScroll: true });
    };
    return el("label", { className: "fpl-answer" }, el("span", { className: "fpl-vh" }, "Antwoord op deze kaart"), field);
  }

  /** The text a card is headed by: a span's quote, an address's text, a bundle's pieces, a lost fact's note; never its id. */
  function headOf(row) {
    if (row.labels?.[0] === "parts") return leavesOf(row).map((t) => { const r = all.find((x) => x.id === t); return typeof r?.text === "string" ? plain(r.text).trim() : ""; })
      .filter(Boolean).join(" … ");
    if (typeof row.text === "string") return plain(row.text).trim();
    const at = anchorsOf(row.id)[0];
    return at ? at.textContent.replace(/\s+/g, " ").trim() : row.note || "een feit";
  }
  /** A card's kind, its chip: its own first label, else that of the first fact or relation hanging from it. */
  const kindOfCard = (row) => (row.labels?.[0] !== "parts" && row.labels?.[0]) || facts(row.id).find((r) => r.labels?.length)?.labels[0] || null;

  /** A group on a card (board V3b): its square and name; under the mouse its members light, spans and cards. */
  function groupChip(g) {
    const c = el("span", { className: "fpl-gchip", title: roleOf(g) ? `${groupName(g)} · ${roleOf(g)}` : groupName(g) },
      el("span", { className: "fpl-sq" }), groupName(g));
    c.dataset.group = g.id;
    c.onmouseenter = () => lightGroup(g.id);
    c.onmouseleave = () => lightGroup(null);
    return c;
  }
  /**
   * Light a group's members, their spans, cards and graph cards, in a
   * class of their own: is-hot opens a card over the one below it, and
   * a group lights several at once.
   */
  function lightGroup(gid) {
    for (const n of document.querySelectorAll(".fpl-ingroup")) n.classList.remove("fpl-ingroup");
    const g = gid && all.find((r) => r.id === gid);
    if (!g) return;
    const ids = new Set(g.targets.flatMap(groupOf));
    for (const id of ids) { const a = anchorsOf(id); for (const e of a.length ? a : [place(id)].filter(Boolean)) e.classList.add("fpl-ingroup"); }
    for (const n of [...margin.querySelectorAll(".fpl-card"), ...(plane?.querySelectorAll(".fpl-node") ?? [])])
      if (ids.has(n.dataset.id)) n.classList.add("fpl-ingroup");
  }

  /**
   * The card of a span (board F). At rest two rows: a head (the dot in the
   * row's colour, the first words of the quote, the kind as a chip, and
   * the card's Graph and ⋯, whose place is kept while they are hidden so
   * nothing moves when they show) and a meta line (who, the relations by
   * their other end, "n reacties"), and the argument's tree, folded, in
   * reach of a pick. Open (a click, its menu, a ledger row, "n reacties")
   * or holding the focus, the thread shows under it, then one field,
   * Antwoord…; hover alone shows the icons and opens the clamped note over
   * the card below, as board E. An open card is laid out open and pushes
   * the rest down. A row lost from the text is one amber line that says so.
   */
  function cardOf(row) {
    const gone = orphan(row), st = gone ? "weg" : state[row.id], cls = row.mine ? "is-mine" : "is-vers";
    const card = el("div", { className: `fpl-card ${row.mine ? "mine" : ""} ${st !== "vers" ? "lost" : ""}` });
    card.dataset.id = row.id;
    card.style.setProperty("--lc", tone(row));
    if (row.id === openId) card.classList.add("is-open");
    const head = headOf(row);
    const readings = typeof row.text === "string" || st !== "vers" ? []
      : all.filter((r) => r !== row && addressed(r) && shows(r) && r.targets[0] === row.targets[0]);
    const { rels, msgs } = readings.length ? { rels: [], msgs: [] } : about(row.id);
    if (relates(row) && typeof row.text !== "string" && !readings.length) rels.unshift(row);   // a fact on an address may itself relate
    const n = readings.length ? 0 : replies(row.id);
    const graphBtn = el("button", { type: "button", className: "fpl-ib", ariaLabel: "Graph van deze kaart", title: "Graph van deze kaart" }, ico("graph"));
    graphBtn.onclick = (ev) => { ev.stopPropagation(); graph(row.id); };
    const more = el("button", { type: "button", className: "fpl-ib fpl-card-more", ariaLabel: "Meer acties voor deze kaart", title: "Meer acties" }, ico("more"));
    more.ariaHasPopup = "menu";
    more.ariaExpanded = String(menuOf === row.id && !cardMenu.hidden);
    more.onclick = (ev) => { ev.stopPropagation(); openMenu(row.id); };
    if (st !== "vers") {   // board B: one amber line, the same card underneath
      const what = gone ? "wijst nergens heen" : st === "dubbel" ? "staat meer dan eens in de tekst" : "staat niet meer in de tekst";
      card.append(el("div", { className: "fpl-cardhead" },   // no Graph: a lost row has no place to draw from
        el("p", { className: "fpl-lostline" }, el("b", {}, st === "dubbel" ? "dubbel" : "kwijt"), " · ",
          el("span", { className: "fpl-excerpt" }, `“${clip(head, 44)}”`), ` ${what}`), more));
    } else {
      const dot = el("span", { className: "fpl-dot" });
      const kind = readings.length ? null : kindOfCard(row);
      card.append(el("div", { className: "fpl-cardhead" }, dot, el("span", { className: "fpl-title", title: clip(head, 300) }, head),
        kind ? chip(kind, "is-kind") : null, graphBtn, more));
    }
    if (row.labels?.[0] === "parts") card.append(piecesOf(row, card));
    if (readings.length) {
      const differ = new Set([row, ...readings].map((r) => r.labels?.[0] ?? "")).size > 1;
      const been = new Set([row, ...readings].map((r) => r.id));
      card.append(el("p", { className: "fpl-meta" }, el("b", {}, `${readings.length + 1} ${differ ? "lezingen" : "rijen"}`)),
        // each reading is a whole fact: its replies, its argument, data-fact for a pick
        el("ol", { className: "fpl-msgs fpl-readings" }, ...[row, ...readings].map((r) => {
          const v = msgView(r, row.id, been);
          v.classList.add("fpl-reading");
          return v;
        })));
    } else if (row.note && st === "vers") card.append(el("p", { className: "fpl-note" }, row.note));
    const gs = st === "vers" ? groupsOf(row.id) : [];
    if (gs.length) card.append(el("p", { className: "fpl-groups" }, ...gs.map(groupChip)));
    // the meta line: what always shows, then "n reacties" at rest or the block's address open, never both
    const base = [author(row) ? el("b", {}, author(row)) : null, ...rels.map((r) => relLine(r, row.id)),
      // a bundle of ours takes more pieces: the next Alt-selects join it
      row.labels?.[0] === "parts" && row.mine ? button("Deel erbij…", (ev) => { ev.stopPropagation(); arm(row.id); }, "fpl-end fpl-arm") : null].filter(Boolean);
    const u = st === "vers" ? place(row.id)?.closest(".fpl-p") : null, sep = base.length ? " · " : "";
    const opener = n ? button(`${n} ${n === 1 ? "reactie" : "reacties"}`, (ev) => { ev.stopPropagation(); openId = row.id; layout(); hot(row.id); }, "fpl-end") : null;
    if (opener) opener.title = "Open de thread";   // a card of ours opens its editor on a click; this opens its thread
    const tail = [n ? el("span", { className: "fpl-count-r" }, sep, opener) : null,
      u?.dataset.n ? el("span", { className: "fpl-where" }, sep, addr(u)) : null].filter(Boolean);
    if ((base.length || tail.length) && !readings.length)
      card.append(el("p", { className: "fpl-meta" }, ...base.flatMap((x, i) => [i ? " · " : "", x]), ...tail));
    card.append(...ledgerRows(rels, row.id));
    // the argument stays in reach at rest (feedback 19): its tree's branches are ends a pick may click
    const box = readings.length ? null : argBox(row.id);   // a reading's message drew it
    if (box) card.append(box);
    const over = new Map();   // a bundle inside has no card: its facts hang here, under its name
    if (row.labels?.[0] === "parts") for (const d of treeOf(row).slice(1).filter(bundleOf)) for (const r of facts(d)) { msgs.push(r); over.set(r.id, d); }
    const been = new Set([row.id, ...msgs.map((m) => m.id)]);
    const thread = el("div", { className: "fpl-thread" });
    if (msgs.length > 0 && n > LONG_THREAD && !unfolded.has(row.id))
      thread.append(button(`${n} reacties`, (ev) => { ev.stopPropagation(); unfolded.add(row.id); openId = row.id; layout(); }, "fpl-link fpl-thread-fold"));
    else if (msgs.length) thread.append(el("ol", { className: "fpl-msgs" }, ...msgs.map((m) => {
      const v = msgView(m, row.id, been);
      if (over.has(m.id)) v.prepend(el("div", { className: "fpl-mhead" }, "over deel ", el("code", {}, over.get(m.id))));
      return v;
    })));
    thread.append(answerField(row.id));
    card.append(thread);
    card.onmouseenter = () => hot(row.id);
    card.onmouseleave = () => hot(null);
    card.onclick = (ev) => {
      if (picking || ev.target.closest("button, a, input, label, details, .fpl-editor, .fpl-ask")) return;
      const m = anchorsOf(row.id)[0];
      m && seen(m).scrollIntoView({ block: "center", behavior: "smooth" });
      if (row.mine && (m || gone)) { edit(row, card); return; }   // a lost fact of ours: open it to delete or rewrite
      if (openId !== row.id) { openId = row.id; layout(); hot(row.id); }
    };
    return card;
  }

  /* ---- a card's menu ⋯ (board F): Verbind met…, Graph, Toon beide, Verwijder ---- */

  let openId = null;   // the card laid out open: its thread shows and the cards below make room
  let menuOf = null;   // the id of the card whose menu is open
  const cardMenu = el("div", { className: "fpl-annot-ui fpl-menu fpl-cardmenu", hidden: true, role: "menu", ariaLabel: "Acties voor deze kaart" });
  const cardEl = (id) => margin.querySelector(`.fpl-card[data-id="${CSS.escape(id)}"]`);
  /**
   * Open the menu of a card, left of it as on board F (under its ⋯ where
   * there is no room), with the card laid out open. Its Verbind met… arms
   * a pick, as the key l and a press on the card's knob do.
   */
  function openMenu(id) {
    const was = menuOf === id && !cardMenu.hidden;
    shut();
    if (was) return;
    if (openId !== id) { openId = id; layout(); }
    const card = cardEl(id), row = all.find((r) => r.id === id);
    if (!card || !row) return;
    hot(id);
    menuOf = id;
    fillCardMenu(row);
    cardMenu.hidden = false;
    const btn = card.querySelector(".fpl-card-more");
    btn.ariaExpanded = "true";
    const r = card.getBoundingClientRect(), b = btn.getBoundingClientRect(), w = 240, left = r.left - 8 - w >= 8;
    cardMenu.style.width = `${w}px`;
    cardMenu.style.left = `${scrollX + (left ? r.left - 8 - w : Math.max(8, b.right - w))}px`;
    cardMenu.style.top = `${scrollY + (left ? r.top - 2 : b.bottom + 6)}px`;
    cardMenu.querySelector("button:not([aria-disabled='true'])")?.focus({ preventScroll: true });
  }
  /** An item of a menu: an icon, its name, and a key or a reason after it. */
  const entry = (name, text, onclick, after) => {
    const b = button("", onclick, "fpl-item");
    b.role = "menuitem";
    b.append(ico(name), text, ...after ? [after] : []);
    return b;
  };
  /**
   * Pull a row into the tray of pulled sentences, group/gepakt (board
   * V3d), or lay it back: the tray is a group row of this browser, made
   * on the first pull and let go with its last sentence, since a group
   * holds one member at least. A tray of the sidecar only reads.
   */
  function pull(id) {
    const tray = all.find((r) => r.labels?.[0] === TRAY), ts = tray?.targets ?? [], back = ts.includes(id);
    const rest = back ? ts.filter((t) => t !== id) : [...ts, id];
    if (tray && !rest.length) save(tray, "delete");
    else save(tray ?? {}, { note: tray?.note ?? "", labels: tray?.labels ?? [TRAY], targets: rest });
    draw();
    toast(back ? "Teruggelegd" : "Gepakt");
  }
  /** Put a row in a group of ours and out of the tray (board V3c); a group of the sidecar only reads. */
  function join(id, g) {
    if (!g?.mine) { toast("Een groep uit de sidecar wijzig je met lit facts"); return; }
    const tray = all.find((r) => r.labels?.[0] === TRAY), rest = tray?.targets.filter((t) => t !== id);
    if (!g.targets.includes(id)) save(g, { targets: [...g.targets, id] });
    if (tray?.mine && rest.length < tray.targets.length) rest.length ? save(tray, { targets: rest }) : save(tray, "delete");
    draw();
    toast(`In “${groupName(g)}”`);
  }
  /** While the tree is open, the tray's sentences are dashed in the text, as pulled out of it (board V3c). */
  function pulled(on) {
    for (const m of body.querySelectorAll(".fpl-pulled")) m.classList.remove("fpl-pulled");
    for (const t of on ? all.find((r) => r.labels?.[0] === TRAY)?.targets ?? [] : []) for (const m of anchorsOf(t)) m.classList.add("fpl-pulled");
  }
  function fillCardMenu(row) {
    const tray = all.find((r) => r.labels?.[0] === TRAY);
    const ends = [...new Set([row, ...facts(row.id)].flatMap((r) => (r.targets ?? []).slice(typeof r.text === "string" ? 0 : 1)))]
      .filter((t) => place(t) && t !== row.id).slice(0, 3);
    const mine = !!row.mine, n = replies(row.id);
    const del = entry("wipe", "Verwijder", () => {
      if (!mine) { toast("Een rij uit de sidecar verwijder je met lit facts, niet hier"); return; }
      del.replaceWith(el("div", { className: "fpl-item fpl-confirm" }, n ? `Verwijderen? ${n} ${n === 1 ? "reactie wijst" : "reacties wijzen"} dan nergens heen.` : "Verwijderen?",
        button("Verwijder", () => { shut(); save(row, "delete"); openId = null; draw(); toast("Verwijderd"); }, "fpl-danger"),
        button("Nee", () => fillCardMenu(row))));
      cardMenu.querySelector(".fpl-confirm button")?.focus();
    });
    if (!mine) del.title = "Uit de sidecar";
    del.classList.add("fpl-danger");
    if (!mine) del.ariaDisabled = "true";
    cardMenu.ariaLabel = "Acties voor deze kaart";
    cardMenu.replaceChildren(...[
      Object.assign(entry("link", "Verbind met…", () => { shut(); pick(row.id); }, el("kbd", {}, "l")),
        { title: "Of sleep het bolletje naar een andere span: steunt, valt aan, zelfde als" }),
      entry("graph", "Graph van deze kaart", () => { shut(); graph(row.id); }),
      ...ends.map((t) => entry("fold", `Toon beide · ${clip(said(t), 22)}`, () => { shut(); both(row.id, t); })),
      tray && !tray.mine ? null : entry("tray", tray?.targets?.includes(row.id) ? "Leg terug" : "Pak", () => { shut(); pull(row.id); }),
      entry("group", "Groepeer…", () => { shut(); graph(row.id).then(() => plane?.group(row.id)); }),
      el("hr"),
      del].filter(Boolean));
  }
  cardMenu.onkeydown = (e) => {
    const items = [...cardMenu.querySelectorAll("button")];
    const i = items.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length]?.focus();
    } else if (/^[1-5]$/.test(e.key) && cardMenu.querySelector("kbd")?.textContent === "1") {   // the chooser's kinds
      e.preventDefault();
      [...cardMenu.querySelectorAll(".fpl-item")].find((x) => x.querySelector("kbd")?.textContent === e.key)?.click();
    } else if (e.key === "l" && menuOf) {
      e.preventDefault();
      const id = menuOf;
      shut();
      pick(id);
    }
  };

  /**
   * The pieces of a parts row as chips, in its order. On a row of ours a
   * chip's × lets the piece go, a loose span again; the last but one
   * asks first, since a bundle of one is none and goes whole.
   */
  function piecesOf(row, card) {
    const text = (t) => { const r = all.find((x) => x.id === t);
      return typeof r?.text === "string" ? plain(r.text).trim().slice(0, 40) : t; };
    // a bundle in the bundle: its pieces in brackets, and a click writes a fact about it
    const gist = (t) => !bundleOf(t) ? el("span", { className: "fpl-gist" }, text(t))
      : el("button", { type: "button", className: "fpl-gist fpl-inner", title: `Feit over ${t}`, onclick: (ev) => {
        ev.stopPropagation(); edit({ targets: [t] }, null, ev.currentTarget.getBoundingClientRect()); } },
        "⟨", ...leavesOf(bundleOf(t)).flatMap((u, j) => [j ? " · " : "", text(u).slice(0, 16)]), "⟩");
    return el("div", { className: "fpl-pieces" }, ...(row.targets ?? []).map((t, i) => el("span",
      { className: `fpl-chip fpl-piece ${state[t] === "vers" ? "" : "is-lost"}`, title: t }, gist(t),
      row.mine ? button("×", (ev) => {
        ev.stopPropagation();
        const rest = row.targets.filter((_, j) => j !== i);
        if (rest.length > 1) { save(row, { targets: rest }); draw(); return; }
        if (card.querySelector(".fpl-ask")) return;
        const n = all.filter((r) => typeof r.text !== "string" && r.targets?.[0] === row.id).length;   // kept, they name nothing then
        const left = n ? ` ${n} ${n > 1 ? "feiten" : "feit"} over de bundel ${n > 1 ? "blijven" : "blijft"} bewaard maar ${n > 1 ? "wijzen" : "wijst"} dan nergens heen.` : "";
        const ask = el("div", { className: "fpl-bar fpl-ask" }, `Dan blijft één deel over: de bundel opheffen?${left}`,
          button("Ja, hef op", () => { save(row, "delete"); if (adding === row.id) adding = null; draw();
            toast(`Bundel opgeheven: de delen zijn losse spans${n ? ` · ${n} ${n > 1 ? "feiten wijzen" : "feit wijst"} nergens heen` : ""}`); }, "fpl-go"),
          button("Nee", () => { ask.remove(); layout(); }));
        card.append(ask);
        if (wide()) makeRoom(card);
      }, "fpl-unpiece") : null)));
  }

  /* ---- arguments: supports and attacks rows between rows ---- */

  const ARGUING = ["supports", "attacks"];
  const kindOf = (r) => ARGUING.includes(r.labels?.[0]) ? r.labels[0] : null;
  /** The supports and attacks rows ending at an id: a claim's grounds and attackers, an inference's undercuts. */
  const grounds = (id) => all.filter((r) => kindOf(r) && shows(r) && (r.targets ?? []).slice(1).includes(id));
  /** One line of what an id says: its row's note or text, else the text where it shows, else the id. */
  function gist(id) {
    const r = all.find((x) => x.id === id);
    const s = r?.note || (typeof r?.text === "string" ? plain(r.text) : "") || place(id)?.textContent || "";
    return s.replace(/\s+/g, " ").trim().slice(0, 120) || id;
  }
  /** What a row is called in a sentence: a span by its quote, anything else by its gist. */
  const said = (id) => { const r = all.find((x) => x.id === id); return typeof r?.text === "string" ? plain(r.text).trim() : gist(id); };
  /**
   * The tree read from an id: each ground a branch, + when it supports
   * and − when it attacks; under a branch first the attacks and supports
   * of its inference, then the grounds of its premise. An id met again
   * on its own path is a cycle (the graph allows one) and stops there;
   * one drawn before elsewhere in the tree (a premise two claims share)
   * shows once more, unexpanded, so the tree grows with the rows and not
   * with the paths through them.
   */
  function argTree(id, path, drawn) {
    const ul = el("ul", { className: "fpl-arg" });
    for (const rel of grounds(id)) {
      const src = rel.targets[0], k = kindOf(rel);
      const li = el("li", { className: `fpl-arg-${k}` });
      li.dataset.id = rel.id;
      const go = el("button", { type: "button", className: "fpl-arg-node", title: `${rel.id}: ${src}` },
        el("b", {}, k === "supports" ? "+" : "−"), " ", gist(src));
      go.onclick = (ev) => {
        if (picking) return;
        ev.stopPropagation();
        const e = place(src);
        e ? seen(e).scrollIntoView({ block: "center", behavior: "smooth" }) : toast(`${src} staat niet op deze pagina`);
      };
      li.append(go, weigh(rel));
      if (rel.note) li.append(el("p", { className: "fpl-note" }, rel.note));
      if (path.has(src) || path.has(rel.id)) li.append(el("span", { className: "fpl-lost" }, "kring"));
      else if (drawn.has(rel.id) || drawn.has(src)) li.append(el("span", { className: "fpl-lost" }, "zie boven"));
      else {
        drawn.add(rel.id).add(src);
        const deeper = new Set([...path, rel.id, src]);
        if (grounds(rel.id).length) li.append(el("div", { className: "fpl-arg-under" }, "op de gevolgtrekking", argTree(rel.id, deeper, drawn)));
        if (grounds(src).length) li.append(argTree(src, deeper, drawn));
      }
      ul.append(li);
    }
    return ul;
  }
  /**
   * A branch's weight, 1 to 5 (Kialo's impact), as five dots. On a row
   * of ours a dot sets it and the lit last dot clears it; a sidecar row
   * shows its weight and only `lit facts' changes it. Without a row
   * (rel null: a group of the tree under its claim by order alone), make
   * writes the row a dot asks for.
   */
  function weigh(rel, make) {
    const w = rel?.weight ?? 0, can = rel ? rel.mine : !!make;
    const box = el("span", { className: "fpl-weight", title: w ? `gewicht ${w}` : "geen gewicht" });
    for (let n = 1; n <= 5; n++) {
      const dot = el(can ? "button" : "span", { className: n <= w ? "on" : "" }, "●");
      if (can) {
        dot.type = "button";
        dot.title = n === w ? "gewicht weg" : `gewicht ${n}`;
        dot.onclick = (ev) => {
          if (picking) return;
          ev.stopPropagation();
          if (rel) save(rel, { weight: n === w ? undefined : n });   // undefined: JSON drops the key
          else make(n);
          draw();
        };
      }
      box.append(dot);
    }
    return box;
  }
  const opened = new Set();   // the ids whose tree is open, kept across draws
  /** A claim's count, "2 voor · 1 tegen", over its tree; null when nothing argues about it. */
  function argBox(id) {
    const g = grounds(id);
    if (!g.length) return null;
    const pro = g.filter((r) => kindOf(r) === "supports");
    const sum = (rs) => rs.reduce((n, r) => n + (r.weight ?? 0), 0);
    const con = g.filter((r) => kindOf(r) === "attacks");
    const weighed = g.some((r) => r.weight) ? ` · gewicht ${sum(pro)} : ${sum(con)}` : "";
    const d = el("details", { className: "fpl-args" },
      el("summary", {}, `Argument · ${pro.length} voor · ${con.length} tegen${weighed}`), argTree(id, new Set([id]), new Set([id])));
    d.open = opened.has(id);
    // a new box set open fires toggle too: only a change by hand lays out again
    d.ontoggle = () => { if (d.open === opened.has(id)) return; d.open ? opened.add(id) : opened.delete(id); layout(); };
    d.onclick = (ev) => { if (!picking) ev.stopPropagation(); };
    return d;
  }

  /**
   * The argument read from the groups, for the tree (boards V3c, V4c):
   * every group but the tray, in order of its order/<n> (unnumbered last,
   * as written), each under the group it argues for or against. A group
   * hangs under another by a supports or attacks row between the two
   * (its first target the group, a later one the other), which brings its
   * kind and weight; a bewijs or tegen without one hangs under the last
   * claim before it, by order alone, a line without a sign. An attacks
   * row aimed at such a row is an undercut, listed under the group whose
   * step it attacks, after what hangs from that group. Depth first, so the order a reader drags is
   * the order written back.
   */
  function outline() {
    const gs = all.filter((r) => isGroup(r) && shows(r) && r.labels[0] !== TRAY);
    const num = (g) => Number(g.labels.find((l) => /^order\/\d+$/.test(l))?.slice(6) ?? Infinity);
    gs.sort((a, b) => num(a) - num(b) || all.indexOf(a) - all.indexOf(b));
    const ids = new Set(gs.map((g) => g.id)), up = new Map();
    for (const r of all) {
      const at = kindOf(r) && shows(r) && ids.has(r.targets[0]) && r.targets.slice(1).find((t) => ids.has(t));
      if (at && !up.has(r.targets[0])) up.set(r.targets[0], { parent: at, rel: r, kind: kindOf(r) });
    }
    let claim = null;
    for (const g of gs) {
      const role = roleOf(g);
      if (role === "claim") claim = g;
      else if (claim && !up.has(g.id) && (role === "bewijs" || role === "tegen"))
        up.set(g.id, { parent: claim.id, rel: null, kind: role === "bewijs" ? "supports" : "attacks" });
    }
    for (const id of ids) {   // a ring of rows (the graph allows one) is cut where it closes
      const seen = new Set([id]);
      for (let p = up.get(id)?.parent; p; p = up.get(p)?.parent) if (seen.has(p)) { up.delete(id); break; } else seen.add(p);
    }
    const out = [], under = (pid) => gs.filter((g) => (up.get(g.id)?.parent ?? null) === pid);
    const walk = (g, depth) => {
      const u = up.get(g.id), item = { g, depth, ...u };
      out.push(item);
      for (const c of under(g.id)) walk(c, depth + 1);
      if (u?.rel) for (const x of all.filter((r) => kindOf(r) === "attacks" && shows(r) && r.targets.slice(1).includes(u.rel.id)))
        out.push({ uc: x, depth, on: item });   // after the group's own subtree: its line, from the step, passes left of it
    };
    for (const g of under(null)) walk(g, 0);
    return out;
  }

  /**
   * Connecting (board C). A pick waits for the other end: Verbind met…,
   * the key l, or a press on a knob arms one, and a click on an end, or
   * Tab to it and Enter, asks the kind. The knob may instead be dragged
   * onto the end (on touch after a long press). Either way the chooser
   * then offers verbindt (relates, Enter), steunt, valt aan, zelfde als
   * and citeert (1-5); Esc or a click elsewhere lets go. Alt-Shift-click
   * arms a pick whose kind is known, resumes, which saves at once.
   */
  let picking = null;   // {from, kind}: the next click on an end ends a pick from `from`; kind null asks it there
  let picked = 0;       // when the last pick landed: the gesture's late touchend (pointerDone) is swallowed
  /**
   * The connect in flight, kept as data so that a layout in between
   * draws it again (drawAim): from, the row it starts at; to, the end
   * under the pointer or reached with Tab; x and y, the pointer in page
   * px while the knob is carried; open, once the chooser asks the kind.
   */
  let link = null;
  let drag = null;   // the pointer on a knob: {from, id, x, y, live, touch, moved, timer}
  const HOLD = 350;  // ms: a touch held this long on a knob carries it; a shorter one is a tap, which arms a pick
  /** What a connect may end at: a branch, a fact, a card, a span or an address. */
  const AIMS = "li[data-id], [data-fact], .fpl-card[data-id]:not([data-id='draft']), mark.fact:not([data-id='draft']), .fpl-c[id], .fpl-s[id], .fpl-p[id]";
  const aimOf = (e) => e.dataset.fact ?? (e.matches(".fpl-p, .fpl-s, .fpl-c") ? e.id : e.dataset.id);
  /** The end under a point of the window, or null. */
  const aimAt = (x, y) => {
    const hit = document.elementFromPoint(x, y), k = hit?.closest?.(".fpl-knob");
    if (k) return k.dataset.id;   // another span's knob is that span: dot onto dot connects
    const e = hit?.closest?.(AIMS);
    return e && !e.closest(".fpl-menu") ? aimOf(e) : null;
  };
  /** The text column's right edge, where every line leaves for the margin, in page px. */
  const gutter = () => body.getBoundingClientRect().right + scrollX + 2;

  /** Arm a pick from a row: the next click on an end, or Tab to one and Enter, asks the kind. */
  const pick = (from) => {
    adding = null;   // one armed gesture at a time
    picking = { from, kind: null };
    link = { from, to: null };
    document.body.classList.add("fpl-picking");
    hot(from);
    drawAim();
    toast(`Verbind “${clip(said(from), 28)}”: klik het andere eind, of Tab en Enter. Esc breekt af.`);
  };
  const unpick = () => {
    picking = null;
    document.body.classList.remove("fpl-picking");
    if (link && !link.open) { link = null; drawAim(); hot(null); }
  };
  /** The pick's click: the row under it, from the innermost of a branch, a fact, a card, a span or a block. */
  document.addEventListener("click", (ev) => {
    if (!picking || ev.target.closest?.(".fpl-arm")) return;   // "Deel erbij…" ends the pick itself (arm)
    const at = ev.target.closest?.(picking.kind === "resumes" ? ".fpl-c[id], .fpl-s[id]:not(:has(.fpl-c))" : AIMS);
    if (!at) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();   // the Alt listener below must not see a pick's click
    const to = aimOf(at), { from, kind } = picking;
    picked = performance.now();
    if (!kind) {
      if (to === from) { toast("Dat is hetzelfde eind: kies een ander"); return; }
      chooser(from, to, { x: ev.pageX, y: ev.pageY }, false);
      return;
    }
    unpick();
    connect(from, to, kind);
  }, true);

  /** Save a row of a kind from -> to, unless it is there already; its toast names both ends by their text. */
  function connect(from, to, kind) {
    picked = performance.now();
    if (to === from) { toast("Een rij argumenteert niet over zichzelf"); return; }
    if (all.some((r) => r.labels?.[0] === kind && r.targets?.[0] === from && r.targets?.[1] === to)) { toast("Die rij is er al"); return; }
    save({ targets: [from, to] }, { note: "", labels: [kind] });
    opened.add(to);
    draw();
    toast(`“${clip(said(from), 24)}” ${VERB[kind] ?? kind} “${clip(said(to), 24)}”`);
  }

  /** The chooser's kinds in their keys' order, each with its icon: verbindt is lit's relates. */
  const KINDS = [["relates", "link"], ["supports", "supports"], ["attacks", "attacks"], ["coref", "same"], ["cites", "cites"]];
  /**
   * Ask what kind of row joins from to to: the chooser (board C) in the
   * card menu's place, 23px right of and 16px under the point at, the
   * first kind focused, so Enter saves verbindt. carried: the knob was
   * dragged there, and its line stays at the drop until the answer.
   */
  function chooser(from, to, at, carried) {
    unpick();
    link = { from, to, x: carried ? at.x : null, y: carried ? at.y : null };
    shut();
    link.open = true;
    hot(from);
    drawAim();
    menuOf = null;
    cardMenu.ariaLabel = "Soort verbinding";
    cardMenu.replaceChildren(
      el("header", {}, "Verbind met ", el("b", {}, `“${clip(said(to), 24)}”`), " als"),
      ...KINDS.map(([k, i], n) => entry(i, VERB[k], () => choose(k), el("kbd", {}, String(n + 1)))),
      el("footer", {}, el("kbd", {}, "Enter"), " kiest verbindt · ", el("kbd", {}, "Esc"), " laat los"));
    const w = 248;
    cardMenu.style.width = `${w}px`;
    cardMenu.hidden = false;
    const h = cardMenu.offsetHeight, right = scrollX + document.documentElement.clientWidth - w - 8;
    cardMenu.style.left = `${Math.max(scrollX + 8, Math.min(at.x + 23, right))}px`;
    cardMenu.style.top = `${at.y + 16 + h > scrollY + innerHeight - 8 ? Math.max(scrollY + 8, at.y - h - 8) : at.y + 16}px`;
    cardMenu.querySelector(".fpl-item")?.focus({ preventScroll: true });
  }
  function choose(kind) {
    const { from, to } = link;
    link = null;
    shut();
    drawAim();
    hot(null);
    connect(from, to, kind);
  }

  /**
   * While a pick waits: Tab and the arrows walk the cards in page order
   * (a span and its card are one end), the end lit and scrolled into
   * view; Enter asks the kind. Whether the key was the walk's.
   */
  function walk(ev) {
    const back = ev.key === "ArrowUp" || ev.key === "ArrowLeft" || (ev.key === "Tab" && ev.shiftKey);
    if (!back && !["Tab", "ArrowDown", "ArrowRight", "Enter"].includes(ev.key)) return false;
    ev.preventDefault();
    ev.stopPropagation();
    const { from } = picking;
    if (ev.key === "Enter") {
      if (!link?.to) { toast("Kies eerst het andere eind: Tab of een klik"); return true; }
      const m = anchorsOf(link.to).at(-1), e = m ? seen(m) : cardEl(link.to) ?? document.getElementById(link.to);
      const r = e.getBoundingClientRect();
      chooser(from, link.to, m ? { x: r.right + scrollX, y: r.top + scrollY + r.height / 2 } : { x: r.left + scrollX, y: r.top + scrollY + HEAD }, false);
      return true;
    }
    const ids = [...new Set([...document.querySelectorAll(".fpl-card[data-id]")].map((c) => c.dataset.id))].filter((id) => id !== "draft" && id !== from);
    if (!ids.length) { toast("Geen ander eind op deze pagina"); return true; }
    const i = ids.indexOf(link.to), n = ids.length;
    link.to = ids[i < 0 ? (back ? n - 1 : 0) : (i + (back ? n - 1 : 1)) % n];
    drawAim();
    const m = anchorsOf(link.to)[0];
    (m ? seen(m) : cardEl(link.to))?.scrollIntoView({ block: "nearest" });
    return true;
  }

  /** Where a connect ends when no pointer holds it: a card's dot, else the gutter at its end's line. */
  function aimPoint(to) {
    const c = cardEl(to);
    if (c) { const r = c.getBoundingClientRect(); return { x: r.left + scrollX - 1, y: r.top + scrollY + HEAD }; }
    const at = reach(to), e = !at && document.getElementById(to);
    if (e) { const r = seen(e).getBoundingClientRect(); return { x: gutter(), y: r.top + scrollY + Math.min(r.height, 24) / 2 }; }
    return at && { x: gutter(), y: at.y };
  }
  /**
   * The connect in flight: its end lit, its knob big, and a dashed line
   * from its span's stub at the text's edge: over the margin it runs to
   * the pointer; while the pointer is over the text it stays in the
   * gutter, at the pointer's height, and only a dot follows the pointer,
   * so no line crosses the text.
   */
  function drawAim() {
    for (const n of document.querySelectorAll(".fpl-target")) n.classList.remove("fpl-target");
    for (const n of lines.querySelectorAll(".fpl-aim")) n.remove();
    for (const n of lines.querySelectorAll(".fpl-knob.is-drag")) n.classList.remove("is-drag");
    document.body.classList.toggle("fpl-linking", !!link);
    if (!link) return;
    const to = link.to, q = to && CSS.escape(to);
    if (to) for (const e of [...anchorsOf(to).map(seen), ...document.querySelectorAll(`.fpl-card[data-id="${q}"], li[data-id="${q}"], [data-fact="${q}"]`),
      ...all.some((r) => r.id === to) ? [] : [document.getElementById(to)]])
      if (e && !e.closest(".fpl-menu")) e.classList.add("fpl-target");
    lines.querySelector(`.fpl-knob[data-id="${CSS.escape(link.from)}"]`)?.classList.add("is-drag");
    const from = reach(link.from), end = link.x != null ? { x: link.x, y: link.y } : to && aimPoint(to);
    if (!from || !end || !lines.isConnected) return;
    const gx = gutter(), { x, y } = end, k = (x - gx - 6) / 2;
    svg("path", { class: "fpl-aim fpl-aim-line", d: x > gx + 6 ? `M${gx},${from.y} h6 C${gx + 6 + k},${from.y} ${x - k},${y} ${x},${y}`
      : `M${gx},${from.y} C${gx + 28},${from.y} ${gx + 28},${y} ${gx},${y}` }, link.from);
    if (link.x != null) svg("circle", { class: "fpl-aim fpl-aim-dot", cx: x, cy: y, r: 6 }, link.from);
  }

  /** The knob leaves its place: the line and its dot follow the pointer from here. */
  function carry() {
    drag.live = true;
    link = { from: drag.from, to: null, x: drag.x + scrollX, y: drag.y + scrollY };
    dropStretch();   // a stretch by keys waiting on another knob
    stretching = stretchOf(drag.from);   // null when its row is no span in the text: then the knob only connects
    document.body.classList.add("fpl-dragging");
    hot(drag.from);
    drawAim();
  }
  function dragMove(ev) {
    if (ev.pointerId !== drag?.id || drag.cancelled) return;
    if (!drag.live) {
      const far = Math.hypot(ev.clientX - drag.x, ev.clientY - drag.y);
      if (drag.touch) { if (far > 8) drag.moved = true; return; }   // a touch that wanders before HOLD carries nothing
      if (far < 4) return;
      carry();
    }
    const st = stretching;
    if (st && onGround(st, ev.clientX, ev.clientY)) {   // along its own text: a stretch, no line to follow the pointer
      if (st.row.mine) {
        link.to = link.x = link.y = null;
        st.end = endAt(st, ev.clientX, ev.clientY);
        paintStretch();
        drawAim();
        return;
      }
      if (!drag.told) { drag.told = true; toast(`${SIDECAR}; slepen verbindt`); }
    } else if (st && st.end !== st.e) { st.end = st.e; paintStretch(); }   // off its text: the span as it was
    for (const o of document.querySelectorAll(".fpl-plane .is-over")) o.classList.remove("is-over");
    intoTree(ev.clientX, ev.clientY)?.classList.add("is-over");
    const to = aimAt(ev.clientX, ev.clientY);
    link.x = ev.pageX;
    link.y = ev.pageY;
    link.to = to === drag.from ? null : to;
    drawAim();
  }
  /** The drop: on an end the chooser asks the kind; on itself or on nothing it lets go, and says so. */
  function dragEnd(ev) {
    if (ev.pointerId !== drag?.id) return;
    for (const [t, f] of DRAG) removeEventListener(t, f);
    clearTimeout(drag.timer);
    const d = drag;
    drag = null;
    document.body.classList.remove("fpl-dragging");
    if (!d.live) { if (ev.type === "pointerup" && !d.moved) pick(d.from); return; }
    picked = performance.now();
    const eat = (e) => { e.stopImmediatePropagation(); e.preventDefault(); };   // the click a drag ends in is the drop's
    addEventListener("click", eat, { capture: true, once: true });
    setTimeout(() => removeEventListener("click", eat, { capture: true }), 0);
    if (d.cancelled) return;   // Esc let it go already
    const st = stretching, up = ev.type === "pointerup";
    if (st?.row.mine && up && onGround(st, ev.clientX, ev.clientY)) { link = null; keepStretch(); drawAim(); hot(null); return; }
    dropStretch();
    const into = up && intoTree(ev.clientX, ev.clientY);
    for (const o of document.querySelectorAll(".fpl-plane .is-over")) o.classList.remove("is-over");
    if (into) {   // the tree's tray pulls the span, a group's block takes it in
      link = null; drawAim(); hot(null);
      const tray = all.find((r) => r.labels?.[0] === TRAY);
      if (into.dataset.group) join(d.from, all.find((r) => r.id === into.dataset.group));
      else if (tray?.targets.includes(d.from)) toast("Al gepakt");
      else if (tray && !tray.mine) toast("De bak uit de sidecar wijzig je met lit facts");
      else pull(d.from);
      return;
    }
    const to = up ? aimAt(ev.clientX, ev.clientY) : null;
    if (to && to !== d.from) { chooser(d.from, to, { x: ev.pageX, y: ev.pageY }, true); return; }
    link = null;
    drawAim();
    hot(null);
    toast(!up ? "Slepen afgebroken" : !to ? "Losgelaten naast een span, kaart of feit: niets verbonden"
      : st && !st.row.mine ? `${SIDECAR}; niets verbonden` : "Losgelaten op de eigen span: niets verbonden");
  }
  /** Where a carried knob would land in the tree: its tray, or a group's block. */
  const intoTree = (x, y) => (plane?.view === "boom" && document.elementFromPoint(x, y)?.closest?.(".fpl-tray, .fpl-tblock[data-group]")) || null;
  /** Esc while a knob is carried: the stretch put back and the connect let go; the drop that follows does nothing. */
  function cancelDrag() {
    const moved = stretching && stretching.end !== stretching.e;
    drag.cancelled = true;
    dropStretch();
    link = null;
    drawAim();
    hot(null);
    document.body.classList.remove("fpl-dragging");
    toast(moved ? "Teruggezet" : "Slepen afgebroken");
  }
  const DRAG = [["pointermove", dragMove], ["pointerup", dragEnd], ["pointercancel", dragEnd]];

  /**
   * Stretching (board D). The same knob, carried along the text of its
   * own block (its .fpl-p) instead of onto another end, moves the end of
   * its span there, a whole word at a time; only the end moves, never
   * past the block, and a span keeps one word. While carried the part
   * gained is washed and underlined dashed (lost words are washed grey),
   * drawn in the lines' svg so the text itself is not touched until the
   * drop; the knob and its line stand at the new end, the card's quote
   * follows, and a tip says "+ n woorden · loslaten bewaart · Esc zet
   * terug". Letting go there saves the row with its text, prefix and
   * suffix read anew from the shown text, as a selection makes them, so
   * the quote finder finds it once; Esc puts it back. Where the pointer
   * is let go decides (PSJ's choice 1): over another span, a card, a
   * fact or a knob, or text of another block, the knob connects as
   * before. A bundle's knob stretches the piece it ends, as a single
   * span. A span of the sidecar is lit's to change: its knob only
   * connects, and says why once it passes over its own text. Shift with
   * the arrows on a focused knob stretches by a word, shown the same
   * way; Enter saves, Esc puts back.
   */
  let stretching = null;   // {id, row, ix, s, e, end, block, hi, keys}: id the knob's card, row the span it moves, [s, e) its text in ix, end the end shown, hi its block's end
  const SIDECAR = "Een span uit de sidecar rek je niet: die verandert alleen met lit";
  const tip = el("div", { className: "fpl-annot-ui fpl-tip", role: "status" });
  const words = (t) => t.split(" ").filter(Boolean).length;
  /** The box of shown character i in the window, or null. */
  const charBox = (ix, i) => {
    const [n, o] = ix.from[i] ?? [];
    if (!n) return null;
    const r = document.createRange();
    r.setStart(n, o);
    r.setEnd(n, o + 1);
    return r.getBoundingClientRect();
  };

  /** What a knob would stretch, or null when its row is no span drawn in a block (a fact on an address only connects). */
  function stretchOf(id) {
    const at = reach(id), row = all.find((r) => r.id === at?.tail?.dataset?.id);
    const block = at?.tail?.closest?.(".fpl-p"), ix = typeof row?.text === "string" && block && shown();
    const got = ix && find(ix, row);
    if (!Array.isArray(got)) return null;
    const r = document.createRange();
    r.selectNodeContents(block);
    return { id, row, ix, s: got[0], e: got[1], end: got[1], block, hi: bounds(ix, r)[1] };
  }
  /** Whether a point of the window is a stretch's own ground: text of its block, outside every span but its own. */
  function onGround(st, x, y) {
    const hit = document.elementFromPoint(x, y), m = hit?.closest?.("mark.fact");
    return !!hit && st.block.contains(hit) && (!m || groupOf(st.id).includes(m.dataset.id));
  }
  /**
   * The shown index past the word under a point: the span's own end
   * while the point is in its last word, at least past its first word,
   * at most its block's end.
   */
  function endAt(st, x, y) {
    const { ix, s, e, hi } = st, flat = ix.flat;
    const pos = document.caretPositionFromPoint?.(x, y), cr = !pos && document.caretRangeFromPoint?.(x, y);
    if (!pos && !cr) return st.end;
    const r = document.createRange();
    r.setStart(pos ? pos.offsetNode : cr.startContainer, pos ? pos.offset : cr.startOffset);
    let k = bounds(ix, r)[0];   // the character right of the caret, or the one left of it when the pointer is there
    const b = charBox(ix, k);
    if (!b || x < b.left || x > b.right) k--;
    while (k > s && flat[k] === " ") k--;
    const past = (i) => { while (i < hi && flat[i] !== " ") i++; return i; };
    const end = past(Math.max(k, s));
    return end === past(e - 1) ? e : Math.min(hi, Math.max(end, Math.min(e, past(s))));
  }
  /** The stretch drawn: the part gained or lost per line, the knob and line at the new end, the card's quote and the tip. */
  function paintStretch() {
    for (const n of lines.querySelectorAll(".fpl-grow")) n.remove();
    tip.remove();
    const st = stretching;
    if (!st) return;
    const { flat, from } = st.ix, cut = st.end < st.e, last = charBox(st.ix, st.end - 1);
    let a = Math.min(st.e, st.end);
    const z = Math.max(st.e, st.end);
    while (a < z && flat[a] === " ") a++;
    if (a < z) {
      const r = document.createRange(), rows = [];
      r.setStart(...from[a]);
      r.setEnd(from[z - 1][0], from[z - 1][1] + 1);
      for (const q of r.getClientRects()) {   // one box per line: the inline boxes of a line overlap by more than half
        if (!q.width || !q.height) continue;
        const o = rows.find((w) => Math.min(w.b, q.bottom) - Math.max(w.t, q.top) > Math.min(w.b - w.t, q.height) / 2);
        if (o) Object.assign(o, { l: Math.min(o.l, q.left), r: Math.max(o.r, q.right), t: Math.min(o.t, q.top), b: Math.max(o.b, q.bottom) });
        else rows.push({ l: q.left, r: q.right, t: q.top, b: q.bottom });
      }
      const cls = cut ? " is-cut" : "";
      for (const w of rows) {
        svg("rect", { x: w.l + scrollX, y: w.t + scrollY, width: w.r - w.l, height: w.b - w.t, class: `fpl-grow fpl-grow-wash${cls}` }, st.id);
        svg("path", { d: `M${w.l + scrollX},${w.b + 0.5 + scrollY} H${w.r + scrollX}`, class: `fpl-grow fpl-grow-line${cls}` }, st.id);
      }
    }
    const card = cardEl(st.id), q = CSS.escape(st.id);
    const knob = lines.querySelector(`.fpl-knob[data-id="${q}"]`), line = lines.querySelector(`.fpl-line[data-id="${q}"]`);
    if (last && knob) { knob.setAttribute("cx", last.right + scrollX + 3); knob.setAttribute("cy", last.bottom - 2 + scrollY); }
    if (last && card && line) line.setAttribute("d", curve(last.bottom - Math.min(last.height, 24) / 2 + scrollY, card));
    const title = card?.querySelector(".fpl-title");
    if (title) {   // the quote as it would be saved, through headOf, so a bundle's card shows its pieces
      const was = all;
      all = all.map((r) => (r.id === st.row.id ? { ...r, text: flat.slice(st.s, st.end) } : r));
      title.textContent = headOf(all.find((r) => r.id === st.id));
      all = was;
    }
    if (st.end === st.e || !last) return;
    const n = words(flat.slice(st.s, st.end)) - words(flat.slice(st.s, st.e)), m = Math.abs(n);
    tip.replaceChildren(`${n < 0 ? "−" : "+"} ${m} ${m === 1 ? "woord" : "woorden"} · `,
      ...(st.keys ? [el("kbd", {}, "Enter"), " bewaart"] : ["loslaten bewaart"]), " · ", el("kbd", {}, "Esc"), " zet terug");
    document.body.append(tip);
    const col = body.getBoundingClientRect(), w = tip.offsetWidth;
    tip.style.top = `${last.bottom + scrollY + 8}px`;
    tip.style.left = `${Math.max(col.left, Math.min(last.right - w / 2, col.right - w)) + scrollX}px`;
  }
  /** Put the span back as it was (Esc, a drop elsewhere, a new stretch); the stretch, or null. */
  function dropStretch() {
    const st = stretching;
    if (st) { st.end = st.e; paintStretch(); }
    stretching = null;
    tip.remove();
    return st;
  }
  /** Save the stretch: its text, prefix and suffix read from the shown text, as a selection makes them. */
  function keepStretch() {
    const st = stretching;
    if (!st) return;
    if (st.end === st.e) { dropStretch(); toast("Losgelaten op de eigen span: niets veranderd"); return; }
    const { flat } = st.ix, n = words(flat.slice(st.s, st.end)) - words(flat.slice(st.s, st.e));
    const got = { text: flat.slice(st.s, st.end), prefix: flat.slice(Math.max(0, st.s - AROUND), st.s), suffix: flat.slice(st.end, st.end + AROUND) };
    if (!Array.isArray(find(st.ix, { ...st.row, ...got }))) { dropStretch(); toast("Zo staat de tekst vaker op de pagina: niet gerekt"); return; }
    stretching = null;
    tip.remove();
    save(st.row, got);
    draw();
    toast(n > 0 ? `${n} ${n === 1 ? "woord" : "woorden"} erbij` : n < 0 ? `${-n} ${n === -1 ? "woord" : "woorden"} eraf` : "Gerekt");
  }
  /** Shift and an arrow on a focused knob: its span's end a word on (d 1) or back (d -1), shown as a drag shows it. */
  function nudge(id, d) {
    if (stretching?.id !== id) {
      dropStretch();
      const st = stretchOf(id);
      if (!st) { toast("Hier valt niets te rekken: dit eind is geen span in de tekst"); return; }
      if (!st.row.mine) { toast(SIDECAR); return; }
      stretching = { ...st, keys: true };
      hot(id);
    }
    const st = stretching, { flat } = st.ix;
    let i = st.end;
    if (d > 0) { while (i < st.hi && flat[i] === " ") i++; while (i < st.hi && flat[i] !== " ") i++; }
    else { while (i > st.s && flat[i - 1] !== " ") i--; while (i > st.s && flat[i - 1] === " ") i--; }
    if (i === st.end || i <= st.s) { toast(d > 0 ? "Het blok houdt hier op: verder rekt de span niet" : "Een span houdt minstens één woord"); return; }
    st.end = i;
    paintStretch();
  }

  /* ---- the graph: rows and what they name, laid out by force ---- */

  /* query: begin. Self-contained: tests/test_query_js.py runs this block in node against tests/query_cases.json. */
  const QUERY = (() => {
    const RELS = new Set(["because", "supports", "attacks", "contradicts", "supersedes", "checkedBy", "cites", "relates", "resumes"]);
    const SETS = new Set(["coref", "parts", "group"]);
    const KEYS = ["label", "layer", "by", "text", "has", "gives"];
    const LAYERS = ["span", "fact", "thread", "argument", "tfa", "coref", "group", "relation"];
    const CHAIN_BUDGET = 100000;   // steps one chain walk may take, rather than freeze the tab (lit's facts.CHAIN_BUDGET)
    const strs = (v) => Array.isArray(v) && v.every((x) => typeof x === "string");
    const first = (r) => (strs(r.labels) && r.labels.length ? r.labels[0] : "");
    const kind = (r) => (first(r).startsWith("group/") ? "group" : first(r));   // lit's facts.kind
    function layer(r, by) {   // lit's facts.layer
      const k = kind(r);
      if ("item" in r) return "span";
      if (k === "parts") return "span";
      if (k === "coref" || k === "group") return k;
      if (k === "resumes" || k.startsWith("tfa/")) return "tfa";
      if (k === "supports" || k === "attacks") return "argument";
      if (RELS.has(k)) return "relation";
      const up = strs(r.targets) && r.targets.length ? by.get(r.targets[0]) : undefined;
      return up !== undefined && !("item" in up) && first(up) !== "parts" ? "thread" : "fact";
    }
    function parse(q) {   // groups of [neg, key, value, chain length, column]; a row is found when one group holds
      const groups = [[]];
      let bar = 0;   // the column of the last "|", 0 before any
      for (const m of q.matchAll(/[^ ]+/g)) {   // terms apart by U+0020 only, as lit
        const term = m[0], col = [...q.slice(0, m.index)].length + 1, neg = term.startsWith("!");   // columns in code points
        if (term === "|") {   // "|" closes a group (PML-TQ's or)
          if (!groups[groups.length - 1].length) throw new Error(`empty group at ${col}`);
          groups.push([]);
          bar = col;
          continue;
        }
        const rest = term.slice(neg ? 1 : 0), i = rest.indexOf(":");
        const key = i < 0 ? "" : rest.slice(0, i);
        let value = i < 0 ? "" : rest.slice(i + 1), n = 0;
        if (i < 0 || !/^[a-z]+$/.test(key)) throw new Error(`no key:value at ${col}`);
        if (!KEYS.includes(key)) throw new Error(`unknown key '${key}' at ${col}`);
        if (!value) throw new Error(`empty value at ${col}`);
        if (key === "has" || key === "gives") {   // R or R+N, N from 1 without leading zeros, past nine digits 1e9
          const p = value.indexOf("+"), length = p < 0 ? "" : value.slice(p + 1);
          if (p >= 0) value = value.slice(0, p);
          if (!RELS.has(value) && !SETS.has(value)) throw new Error(`'${value}' is no relation or set at ${col}`);
          if (p >= 0 && !/^[1-9][0-9]*$/.test(length)) throw new Error(`bad chain length at ${col}`);
          n = p < 0 ? 0 : length.length > 9 ? 1e9 : Number(length);
        }
        if (key === "layer" && !LAYERS.includes(value)) throw new Error(`'${value}' is no layer at ${col}`);
        groups[groups.length - 1].push([neg, key, value, n, col]);
      }
      if (bar && !groups[groups.length - 1].length) throw new Error(`empty group at ${bar}`);
      return groups;
    }
    function query(rows, q) {
      const groups = parse(q), by = new Map(rows.filter((r) => typeof r.id === "string").map((r) => [r.id, r]));
      const add = (m, k, x) => m.set(k, (m.get(k) ?? new Set()).add(x));
      const back = new Map(), ahead = new Map();   // kind -> node -> the nodes an edge joins it to, into it / out of it
      const link = (m, k, a, b) => { if (!m.has(k)) m.set(k, new Map()); add(m.get(k), a, b); };
      for (const r of rows) {   // lit's facts.relation_edges: no node joins itself
        const k = kind(r), t = r.targets;
        if (!strs(t) || !t.length) continue;
        const edges = SETS.has(k) ? t.flatMap((a) => t.filter((b) => a !== b).map((b) => [a, b])) : t.slice(1).filter((b) => b !== t[0]).map((b) => [t[0], b]);
        for (const [a, b] of edges) { link(ahead, k, a, b); link(back, k, b, a); }
      }
      const reaches = (step, x, n) => {   // lit's facts.reaches: x reaches n other nodes, a count that stops there
        const reach = new Set([x]), todo = [x];
        while (todo.length && reach.size <= n) {   // pop outside step?.get(), which would skip it when step is undefined
          const at = todo.pop();
          for (const y of step?.get(at) ?? []) if (!reach.has(y)) { reach.add(y); todo.push(y); }
        }
        return reach.size > n;
      };
      const chain = (step, x, n, col) => {   // lit's facts.chained: a simple path of at least n edges from x along step
        if (!reaches(step, x, n)) return false;   // too few nodes for n edges: no at once
        const path = [x], seen = new Set([x]), nexts = [(step.get(x) ?? new Set()).values()];   // a walk on a stack of its own
        let budget = CHAIN_BUDGET;
        while (nexts.length) {
          const it = nexts[nexts.length - 1];
          let s = it.next();
          while (!s.done && seen.has(s.value)) s = it.next();
          if (s.done) { nexts.pop(); seen.delete(path.pop()); continue; }
          if (path.length === n) return true;
          if (--budget < 0) throw new Error(`chain too long to search at ${col}`);
          path.push(s.value); seen.add(s.value); nexts.push((step.get(s.value) ?? new Set()).values());
        }
        return false;
      };
      const about = (r) => {   // a fact on an address speaks for the address; one on a row, or a relation, only for itself
        const t0 = strs(r.targets) && r.targets.length ? r.targets[0] : null;
        const own = "item" in r || RELS.has(first(r)) || SETS.has(kind(r));
        return own || !t0 || by.has(t0) ? [r.id] : [r.id, t0];
      };
      const holds = (r, key, v, n, col) => {   // bare has:R is has:R+1; bare gives:R is gives:R+1 for a relation, never for a set
        const labels = strs(r.labels) ? r.labels : [];
        switch (key) {
          case "label": return labels.some((x) => x === v || x.startsWith(v + "/"));
          case "layer": return layer(r, by) === v;
          case "by": return r.by === v;
          case "text": return [r.text, r.note].filter((x) => typeof x === "string").join(" ").toLowerCase().includes(v.toLowerCase());
          case "has": return about(r).some((x) => chain(back.get(v), x, n || 1, col));
          default: return Boolean(n || RELS.has(v)) && about(r).some((x) => chain(ahead.get(v), x, n || 1, col));
        }
      };
      return rows.filter((r) => typeof r.id === "string" && groups.some((g) => g.every(([neg, k, v, n, col]) => holds(r, k, v, n, col) !== neg))).map((r) => r.id);
    }
    return { parse, query };
  })();
  /* query: end */
  let asked = "", found = null;   // the query in the field, and the ids it finds (null: no query)
  /** Fade what the query does not find: a card stays when its row or a row in it is found, a span when its card stays. */
  function fade() {
    for (const n of document.querySelectorAll(".fpl-faded")) n.classList.remove("fpl-faded");
    if (!found) { fadeGraph(null); return; }
    const stays = new Set();   // a row found, and the rows its thread hangs from, up to a span or an address
    for (const id of found) for (let r = all.find((x) => x.id === id), been = new Set(); r && !been.has(r.id); been.add(r.id), r = all.find((x) => x.id === r.targets?.[0])) {
      stays.add(r.id);
      for (const g of groupOf(r.id)) stays.add(g);
    }
    fadeGraph(stays);
    for (const c of document.querySelectorAll(".fpl-card")) {   // inline cards too, on a narrow screen
      const ids = [c.dataset.id, ...[...c.querySelectorAll("[data-fact]")].map((x) => x.dataset.fact)];
      if (!ids.some((i) => stays.has(i))) c.classList.add("fpl-faded");
    }
    for (const m of body.querySelectorAll("mark.fact")) if (!stays.has(m.dataset.id)) m.classList.add("fpl-faded");
    for (const e of body.querySelectorAll("[data-tfa-row]")) if (!found.has(e.dataset.tfaRow)) e.classList.add("fpl-faded");
  }

  /**
   * The graph fades as the margin does (feedback 24): a card whose row
   * the query leaves (stays, null without a query) or whose span the
   * filter hides, an id outside the rows while no row that stays names
   * it, and an edge with a faded end.
   */
  function fadeGraph(stays) {
    const hid = (id) => {
      const r = all.find((x) => x.id === id);
      if (stays && !stays.has(id) && (r || !all.some((x) => stays.has(x.id)
        && x.targets?.includes(id)))) return true;
      return typeof r?.text === "string" && !passes(wholeOf(r.id) ?? r);
    };
    const gone = new Set();
    for (const n of plane?.querySelectorAll(".fpl-node") ?? [])
      if (hid(n.dataset.id)) gone.add(n.dataset.id);
    for (const x of plane?.querySelectorAll(".fpl-node, .fpl-edge") ?? []) {
      const { id, a, b } = x.dataset;
      if ([id, a, b].some((i) => gone.has(i))) x.classList.add("fpl-faded");
    }
  }

  const SETKINDS = new Set(["coref", "parts"]);
  /**
   * The page's graph in the layers shown: a node per row and per id a row
   * names, but none for a tfa or resumes row (the lens draws those on the
   * text). A relation row (or coref set) is a node between its ends, rel,
   * an edge in to it from its first target and out to each other; a fact
   * an edge "over" to what it is about; a parts row an edge to each
   * piece. Every edge carries its kind: the relation's label, over, parts,
   * or code for the code graph's; and own, the node of the row it draws,
   * which is about the edge's other end (none on a code edge).
   */
  let code = null;   // the page's code graph (lit graph), when the site shipped one
  const coded = (snap ? Promise.resolve(snap.graph ?? null) : fetch(`${stem}.graph.json`).then((r) => (r.ok ? r.json() : null)))
    .catch(() => null).then((g) => { code = g && Array.isArray(g.nodes) && Array.isArray(g.edges) ? g : null; });
  function graphOf() {
    const nodes = new Map(), edges = [];
    const kinds = new Map((code?.nodes ?? []).map((n) => [n.id, n.kind]));
    const kindOf = (id) => {
      const r = all.find((x) => x.id === id);
      return r ? layerOf(r) : kinds.get(id) ?? (document.getElementById(id) ? "address" : "elders");
    };
    const node = (id) => nodes.get(id) ?? nodes.set(id, { id, kind: kindOf(id), x: 0, y: 0, dx: 0, dy: 0 }).get(id);
    const groups = all.filter((x) => isGroup(x) && shows(x));   // no node: a frame round its members
    for (const g of groups) for (const t of g.targets ?? []) node(t).member = true;
    for (const r of all.filter((x) => shows(x) && !isGroup(x) && !["tfa", "resumes"].includes(sheetOf(x)))) {
      const k = r.labels?.[0] ?? "", ts = (r.targets ?? []).filter(Boolean), n = node(r.id);
      n.row = true;
      if (typeof r.text === "string") continue;
      if (RELATIONS.has(k) || k === "coref") {
        Object.assign(n, { rel: true, kind: k });
        if (k !== "coref" && ts[0])
          edges.push({ a: node(ts[0]), b: n, kind: k, own: n });
        for (const t of k === "coref" ? ts : ts.slice(1))
          edges.push({ a: n, b: node(t), kind: k, w: r.weight ?? 0, own: n });
      } else if (k === "parts")
        for (const t of ts) edges.push({ a: n, b: node(t), kind: k, own: n });
      else if (ts[0])
        edges.push({ a: n, b: node(ts[0]), kind: "over", own: n });
    }
    for (const n of code?.nodes ?? []) node(n.id).label = n.label;
    for (const e of code?.edges ?? []) edges.push({ a: node(e.a), b: node(e.b), kind: "code" });
    return { nodes: [...nodes.values()], edges, groups };
  }
  /**
   * The code block a chunk stands in: the k-th block whose header names
   * it (k from the chunk id). The header is the block's first line,
   * <<[number ]name, read as lit's web.HEAD reads it and normalised as
   * web.norm does; a use (<<name>>) inside another block is no header.
   */
  function chunkBlock(id) {
    const n = code?.nodes.find((x) => x.id === id);
    if (!n || n.kind !== "chunk") return null;
    const norm = (x) => x.split(/\s+/).filter(Boolean).join(" ");
    const head = (b) => {
      const m = /^<<([^<>\n]+)/.exec(b.textContent.replace(/^\s+/, ""));
      return m ? norm(m[1].replace(/^[\d.]+\s+/, "").replace(/>>\+?=?\s*$/, "")) : null;
    };
    const k = Number(id.split(":").at(-1)) || 1;
    return [...body.querySelectorAll('.fpl-p[data-kind="C"]')].filter((b) => head(b) === norm(n.label))[k - 1] ?? null;
  }
  /**
   * A layered drawing, left to right (Sugiyama, Tagawa and Toda 1981):
   * the spans stand in the first column and what is about them to their
   * right, a relation's sign in a column past both its ends, so every
   * edge runs one way (PSJ, 2026-11-03: a grid without direction read
   * as a mess).
   *
   *   ranks   the longest path to a node, over edges whose cycles are
   *           cut where a walk meets its own path; a node no edge
   *           reaches, but a span, moves right, next to what it serves
   *   order   each column by the barycentre of its neighbours, down and
   *           up, then neighbours swapped while that crosses less
   *           (Gansner et al. 1993), the order with the fewest crossings
   *           kept; a group's
   *           members stand together, under the room for its tab
   *   heights each column, in its order, as near the mean of its
   *           neighbours as the gaps allow (pooled adjacent violators)
   *
   * An edge longer than one column passes each column between at a
   * point of its own, so between columns a line meets no card and in a
   * column it runs level beside its own node: no edge crosses a card.
   * ns carry w, h, key (page order, for the first column), grp and
   * first (a span); es are { s, t } from what is about to what is
   * about it, and each gets pts, its route from s to t. Returns the
   * drawing's width and height; each node gets x and y, its middle.
   * Measured 2026-11-03 on the lex page against elkjs 0.9.3's layered,
   * the shelf's choice: elk.bundled.js is 467 KB gzipped (this whole
   * file 83 KB) and took 25 ms to load and 38-50 ms a layout in
   * Chromium; this one well under a millisecond.
   */
  function layered(ns, es, { gap = 18, hgap = 48, tab = 30 } = {}) {
    const ins = new Map(ns.map((n) => [n, []]));
    const outs = new Map(ns.map((n) => [n, []]));
    for (const e of es) outs.get(e.s).push(e);
    const on = new Set(), done = new Set();
    const walk = (n) => {   // depth first: an edge back onto the path turns
      on.add(n);
      for (const e of outs.get(n)) {
        if (on.has(e.t)) e.turn = true;
        else if (!done.has(e.t)) walk(e.t);
      }
      on.delete(n); done.add(n);
    };
    for (const n of ns) if (!done.has(n)) walk(n);
    for (const n of ns) outs.set(n, []);
    for (const e of es) {
      [e.u, e.v] = e.turn ? [e.t, e.s] : [e.s, e.t];
      outs.get(e.u).push(e); ins.get(e.v).push(e);
    }
    const rank = new Map();
    const rk = (n) => {
      if (!rank.has(n))
        rank.set(n, Math.max(0, ...ins.get(n).map((e) => rk(e.u) + 1)));
      return rank.get(n);
    };
    ns.forEach(rk);
    for (const n of ns) {
      const o = outs.get(n);
      if (!n.first && !ins.get(n).length && o.length)
        rank.set(n, Math.min(...o.map((e) => rank.get(e.v))) - 1);
    }
    const L = [];
    const put = (n, r) => { rank.set(n, r); (L[r] ??= []).push(n); };
    for (const n of [...ns].sort((a, b) => a.key - b.key)) put(n, rank.get(n));
    const up = new Map(), down = new Map();
    const add = (m, k, x) => (m.get(k) ?? m.set(k, []).get(k)).push(x);
    for (const e of es) {   // a long edge: a point in each column it passes
      e.chain = [e.u];
      for (let r = rank.get(e.u) + 1; r < rank.get(e.v); r++) {
        const d = { w: 0, h: 2, dummy: true };
        put(d, r); e.chain.push(d);
      }
      e.chain.push(e.v);
      e.chain.slice(1).forEach((b, i) => {
        add(down, e.chain[i], b); add(up, b, e.chain[i]);
      });
    }
    for (let r = 0; r < L.length; r++) L[r] ??= [];
    const pos = new Map();
    const index = () => L.forEach((l) => l.forEach((n, i) => pos.set(n, i)));
    const avg = (xs) => xs.reduce((t, x) => t + x, 0) / xs.length;
    const sweep = (l, nb) => {
      const bc = new Map(l.map((n) => {
        const xs = (nb.get(n) ?? []).map((x) => pos.get(x));
        return [n, xs.length ? avg(xs) : pos.get(n)];
      }));
      const gm = new Map();   // a group's members at their mean, together
      for (const n of l) if (n.grp) add(gm, n.grp, bc.get(n));
      const at = (n) => (n.grp ? avg(gm.get(n.grp)) : bc.get(n));
      const grp = (n) => String(n.grp ?? "");
      l.sort((a, b) => at(a) - at(b) || grp(a).localeCompare(grp(b))
        || bc.get(a) - bc.get(b));
      l.forEach((n, i) => pos.set(n, i));
    };
    const crossings = () => {
      let c = 0;
      for (const l of L) {
        const xs = l.flatMap((a) => (down.get(a) ?? [])
          .map((b) => [pos.get(a), pos.get(b)]));
        for (let i = 0; i < xs.length; i++)
          for (let j = i + 1; j < xs.length; j++)
            if ((xs[i][0] - xs[j][0]) * (xs[i][1] - xs[j][1]) < 0) c++;
      }
      return c;
    };
    const transpose = () => {   // swap neighbours while that crosses less
      let c = crossings();
      for (let more = true; more;) {
        more = false;
        for (const l of L) for (let i = 1; i < l.length; i++) {
          if (l[i].grp !== l[i - 1].grp) continue;   // a group stays one
          [l[i - 1], l[i]] = [l[i], l[i - 1]]; index();
          const d = crossings();
          if (d < c) { c = d; more = true; continue; }
          [l[i - 1], l[i]] = [l[i], l[i - 1]]; index();
        }
      }
      return c;
    };
    index();
    let best = L.map((l) => [...l]), least = crossings();
    for (let round = 0; round < 8 && least; round++) {
      for (let r = 1; r < L.length; r++) sweep(L[r], up);
      for (let r = L.length - 2; r >= 0; r--) sweep(L[r], down);
      const c = transpose();
      if (c < least) { least = c; best = L.map((l) => [...l]); }
    }
    best.forEach((l, r) => { L[r] = l; });
    index();
    // heights: in order, each at least its gap below the last, the leader
    // of a group with room above for the tab
    const lead = (l, i) => (l[i].grp && l[i - 1]?.grp !== l[i].grp ? tab : 0);
    const sep = (l, i) => (l[i - 1].h + l[i].h) / 2 + lead(l, i)
      + (l[i - 1].dummy || l[i].dummy ? 6 : gap);
    const pool = (l, want) => {
      const off = [0], bs = [];
      for (let i = 1; i < l.length; i++) off.push(off[i - 1] + sep(l, i));
      l.forEach((n, i) => {
        bs.push({ s: want(n) - off[i], c: 1, i });
        const m = (b) => b.s / b.c;
        while (bs.length > 1 && m(bs.at(-2)) >= m(bs.at(-1))) {
          const b = bs.pop();
          bs.at(-1).s += b.s; bs.at(-1).c += b.c;
        }
      });
      for (const b of bs) for (let k = 0; k < b.c; k++)
        l[b.i + k].y = b.s / b.c + off[b.i + k];
    };
    for (const l of L) pool(l, () => 0);
    const near = (n) => [...up.get(n) ?? [], ...down.get(n) ?? []];
    for (let round = 0; round < 8; round++)
      for (const l of round % 2 ? [...L].reverse() : L)
        pool(l, (n) => (near(n).length ? avg(near(n).map((x) => x.y)) : n.y));
    const top = Math.min(...L.filter((l) => l.length)
      .map((l) => l[0].y - l[0].h / 2 - lead(l, 0)));
    const W = L.map((l) => Math.max(0, ...l.map((n) => n.w)));
    const X = W.map((_, r) => W.slice(0, r).reduce((t, w) => t + w + hgap, 0));
    L.forEach((l, r) => l.forEach((n) => {
      n.y -= top; n.x = X[r] + W[r] / 2;
    }));
    for (const e of es) {   // level through each column, straight between
      const pts = [];
      for (const n of e.chain) {
        const r = rank.get(n), y = n.y;
        if (n !== e.u) pts.push([X[r], y], [n.x - n.w / 2, y]);
        if (n !== e.v) pts.push([n.x + n.w / 2, y], [X[r] + W[r], y]);
      }
      const route = pts.filter((q, i) => !i
        || q[0] !== pts[i - 1][0] || q[1] !== pts[i - 1][1]);
      e.pts = e.turn ? route.reverse() : route;
    }
    const h = Math.max(0, ...ns.map((n) => n.y + n.h / 2));
    return { w: X.length ? X.at(-1) + W.at(-1) : 0, h };
  }
  /**
   * The graph is a plane beside the page (boards V2b-V2d, V4d): the text
   * column slides to the window's left edge, the margin's cards give way,
   * and the plane takes the rest of the window under the bar, which
   * widens over it. A row is a card with the first words of its quote (a
   * fact its note, a decision its topic), in its colour; a relation row
   * is its kind's sign in a column past its ends, so an undercut has
   * something to aim at; a tfa or resumes row has no node, its lens is
   * the text. The layout is layered (layered), and the plane scrolls
   * when the drawing is wider or taller than it. Dragging a card
   * moves it in this view only: nothing is kept, and the next drawing
   * lays the graph out anew. A click makes the card the centre, and
   * scrolls the page to its span, which Alt ← undoes with the step. The
   * chips at the foot are the kinds of edge, each a toggle; the code
   * graph's edges (a chunk uses a chunk, tangles to a file) start off.
   * Where the window has no room beside the column the plane is a sheet
   * over the page under the folded bar, and a click on the centre
   * closes it first.
   */
  let plane = null;
  const jumps = [];   // the scroll before each jump from the graph, for Alt ←
  const offKinds = new Set(["code"]);   // the edge kinds switched off, for this visit only
  // a card (its kind and two lines of quote), the gap between two in a
  // column, the plane's padding, a relation's sign
  const CW = 168, CH = 58, GY = 18, PAD = 24, SIGN = 18;
  const ARROWS = new Set(["supports", "attacks", "cites", "because", "contradicts", "checkedBy", "supersedes"]);
  const SIGNS = { supports: "supports", attacks: "attacks", coref: "same",
    cites: "cites", checkedBy: "check" };   // the rest by their own names
  const signOf = (k) => SIGNS[k] ?? (k in ICONS ? k : "relates");
  const GREY = new Set(["relates", "cites", "checkedBy", "supersedes", "over", "parts", "code"]);
  const edgeColour = (k) => (GREY.has(k) ? css.getPropertyValue("--fpl-mute").trim() || "#6c757d" : colourOf(k));
  const kindName = (k) => (k === "code" ? "code" : VERB[k] ?? k);
  /**
   * The words of an id outside the page: a refusal's message, a test's
   * name without test_ and its line, any other scheme's path decoded
   * (QA, block 4: a node read "refusal:dedent%20belo…"); null for an id
   * without a scheme.
   */
  const extText = (id) => {
    const m = /^(\w+):(.+)$/.exec(id);
    if (!m) return null;
    let t = m[2];
    try { t = decodeURIComponent(t); } catch { /* a stray % stays as written */ }
    return m[1] === "test" ? t.replace(/:\d+$/, "").replace(/^test_/, "").replace(/_/g, " ") : t;
  };
  const EXT = { refusal: "weigering", test: "test", chunk: "chunk", file: "bestand" };
  /** What a node says: a row's quote, a fact's note, a decision's words, an address's text, a chunk's name, an id's words. */
  function nodeText(n) {
    const r = all.find((x) => x.id === n.id), d = decision(n.id);
    // a span of a lone glyph (a quote mark, a bracket) reads as where it
    // starts in the text: the glyph and the words after it (feedback 24)
    if (typeof r?.text === "string") return /[\p{L}\p{N}]{2}/u.test(r.text)
      ? r.text : `${r.text.trim()} ${r.suffix ?? ""}`.trim();
    if (r) return r.note || (r.labels ?? []).join(" ") || r.id;
    if (d) return d.decision || d.topic || "besluit";
    return n.label ?? (document.getElementById(n.id)?.textContent.trim() || extText(n.id) || n.id);
  }
  /** What a node is, the line over its quote (board V2b): a row's kind, a decision's topic, a place, a chunk, a test. */
  function nodeKind(n) {
    const r = all.find((x) => x.id === n.id), d = decision(n.id);
    if (r) return r.labels?.[0] ? kindName(r.labels[0]) : typeof r.text === "string" ? "span" : "notitie";
    if (d) return d.topic ? `besluit · ${d.topic}` : "besluit";
    return document.getElementById(n.id) ? "plek" : EXT[n.id.split(":")[0]] ?? "elders";
  }
  /**
   * A graph card's kind as a shape beside its colour and its word
   * (feedback 24, for readers who do not tell the colours apart): a span
   * a square and a fact a dot, in its label's colour; a decision, a
   * refusal, a test, a chunk, a file, a place and an id elsewhere each
   * its own outline.
   */
  function glyph(n, r) {
    const ext = { refusal: "kweigering", test: "ktest", chunk: "kchunk",
      file: "kbestand" }[n.id.split(":")[0]];
    const name = r ? (typeof r.text === "string" ? "kspan" : "knote")
      : decision(n.id) ? "kbesluit"
        : document.getElementById(n.id) ? "kplek" : ext ?? "kelders";
    const g = ico(name);
    g.classList.add("fpl-kg");
    if (r) g.style.color = tone(r);
    return g;
  }
  /**
   * Open the plane, with an id selected (a card's Graph) or none (the
   * bar's); a second open selects. view is graph or boom (the tree); the
   * plane open in the other turns to it in place, the column staying put.
   */
  async function graph(id, view = "graph", push = true) {
    await coded;   // the code graph first: a plane drawn before it came would lack the chunks
    if (plane) { if (id) plane.go(id, push); else plane.show(view); return; }
    const opener = document.activeElement;
    const area = el("div", { className: "fpl-plane-area" });
    const foot = el("div", { className: "fpl-plane-foot", role: "group", ariaLabel: "Soorten relaties" });
    const head = el("div", { className: "fpl-scope", role: "radiogroup",
      ariaLabel: "Bereik" });
    const p = plane = el("div", { className: "fpl-annot-ui fpl-graph fpl-plane",
      role: "region", ariaLabel: "Graph" }, head, area, foot);
    let g = null, sel = null, built = "", nodes = [], frames = [], sheet = null;
    // the card the graph stands round, else the whole page (feedback 25):
    // the card it was opened from, or the open card in the margin
    p.centre = id ?? openId ?? null; p.last = p.centre;
    const chosen = new Set();   // the cards Shift-clicked for a group
    const slide = (fn) => {   // the column moves left (or back) in one motion: FLIP on main
      const a = body.getBoundingClientRect().left;
      fn();
      const d = a - body.getBoundingClientRect().left;
      if (d && !matchMedia("(prefers-reduced-motion: reduce)").matches)
        body.animate([{ transform: `translateX(${d}px)` }, { transform: "none" }], { duration: 260, easing: "cubic-bezier(.2,.8,.2,1)" })
          .finished.then(relayout, () => {});   // what was measured mid-slide (arcs, cards, lines) is measured again where it stopped
    };
    const close = () => {
      p.remove(); plane = null; hot(null); pulled(false);
      drawView();
      slide(() => document.body.classList.remove("fpl-beside"));
      layout();
      opener?.focus?.({ preventScroll: true });
    };
    /** Where a node goes on the page: its own place, else that of what it is about, followed up its first targets. */
    const goal = (nid, been = new Set()) => {
      const e = place(nid) ?? chunkBlock(nid);
      if (e || been.has(nid)) return e;
      been.add(nid);
      const r = all.find((x) => x.id === nid);
      return r?.targets?.[0] ? goal(r.targets[0], been) : null;
    };
    const jump = (n, step = false) => {
      const e = goal(n.id);
      if (!e) { toast(`“${clip(nodeText(n), 30)}” staat niet op deze pagina`); return; }
      if (!p.beside) close();
      jumps.push({ y: scrollY, step });
      seen(e).scrollIntoView({ block: "center", behavior: "smooth" });
      hot(n.id);
      toast("Terug: Alt ←");
    };
    /** The nodes and edges shown: a row always, anything else while an edge of a kind switched on reaches it. */
    const shown = () => {
      const es = g.edges.filter((e) => !offKinds.has(e.kind));
      const ends = new Set(es.flatMap((e) => [e.a.id, e.b.id]));
      const ns = g.nodes.filter((n) => (n.row && !n.rel) || n.member || ends.has(n.id));
      const on = new Set(ns.map((n) => n.id));
      const both = es.filter((e) => on.has(e.a.id) && on.has(e.b.id));
      if (!on.has(p.centre)) { p.centre = null; return { ns, es: both }; }
      const near = hood(p.centre, both);
      return { ns: ns.filter((n) => near.has(n.id)),
        es: both.filter((e) => near.has(e.a.id) && near.has(e.b.id)) };
    };
    /**
     * A node's neighbourhood (feedback 25): the node, what an edge joins
     * it to, and each relation reached with all its ends, since a sign
     * without its ends says nothing.
     */
    const hood = (id, es) => {
      const near = new Set([id]);
      for (const e of es)
        if (e.a.id === id || e.b.id === id) near.add(e.a.id).add(e.b.id);
      for (let more = true; more;) {
        more = false;
        for (const e of es) for (const [x, y] of [[e.a, e.b], [e.b, e.a]])
          if (e.own === x && x.rel && near.has(x.id) && !near.has(y.id)) {
            near.add(y.id); more = true;
          }
      }
      return near;
    };
    /** Lay the graph out and draw it, anew when the rows or kinds change. */
    function build() {
      if (p.view === "boom") { tree(); return; }
      const key = `${[...offKinds]}|${p.centre}`;
      if (g && built === key && g.of === all) return;
      built = key;
      g = graphOf(); g.of = all;
      const { ns, es } = shown();
      nodes = ns;
      const grp = new Map();   // a card in two groups stands in the first
      for (const gr of g.groups) for (const t of gr.targets ?? [])
        if (!grp.has(t)) grp.set(t, gr.id);
      for (const n of ns) {
        const at = n.rel ? null : goal(n.id);   // page order, for column one
        Object.assign(n, { w: n.rel ? SIGN : CW, h: n.rel ? SIGN : CH,
          grp: grp.get(n.id), moved: false,
          first: n.kind === "span" || n.kind === "address",
          key: at ? at.getBoundingClientRect().top : 1e9 });
      }
      // each edge from what is about to what is about it, the row it
      // draws; a relation's sign right of the rows it joins, and what
      // else it names (a decision, a test, a file) right of the sign
      const les = es.filter((e) => e.a !== e.b).map((e) => {
        const out = e.own?.rel && e.a === e.own && !e.b.row;
        const t = out ? e.b : e.own ?? e.b;
        return { e, s: t === e.a ? e.b : e.a, t };
      });
      const box = layered(ns, les, { gap: GY });
      const ox = Math.max(PAD + 8, (area.clientWidth - box.w) / 2), oy = PAD;
      for (const n of ns) { n.x += ox; n.y += oy; }
      for (const { e, s, pts } of les)
        e.pts = (s === e.a ? pts : [...pts].reverse())
          .map(([x, y]) => [x + ox, y + oy]);
      area.replaceChildren();
      const sv = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      sv.classList.add("fpl-edges");
      sv.setAttribute("width", Math.max(area.clientWidth, box.w + 2 * ox));
      sv.setAttribute("height", box.h + 2 * PAD);
      const defs = sv.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "defs"));
      for (const k of new Set(es.map((e) => e.kind))) if (ARROWS.has(k)) defs.insertAdjacentHTML("beforeend",
        `<marker id="fpl-to-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" markerUnits="userSpaceOnUse" orient="auto"><path d="M0 1L9 5L0 9z" fill="${edgeColour(k)}"/></marker>`);
      area.append(sv);
      frames = g.groups.map((gr) => ({ g: gr,
        ms: ns.filter((n) => !n.rel && grp.get(n.id) === gr.id) }))
        .filter((f) => f.ms.length).map(frameOf);
      for (const e of es) {
        e.path = sv.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "path"));
        e.path.setAttribute("class", "fpl-edge"); e.path.dataset.kind = e.kind;
        Object.assign(e.path.dataset, { a: e.a.id, b: e.b.id });
        e.path.style.setProperty("--lc", edgeColour(e.kind));
        if (ARROWS.has(e.kind) && (!e.b.rel || e.kind !== e.b.kind)) e.path.setAttribute("marker-end", `url(#fpl-to-${e.kind})`);
      }
      for (const n of ns) {
        const r = all.find((x) => x.id === n.id), text = nodeText(n);
        n.el = n.rel ? sign(n, r) : el("button", { type: "button",
          className: `fpl-node${r ? "" : " is-ext"}`, title: text },
        el("span", { className: "fpl-nkind" }, glyph(n, r), nodeKind(n)),
        el("span", { className: "fpl-nq" }, clip(text, 120)));
        n.el.dataset.id = n.id;
        area.append(n.el);
        grab(n);
      }
      place2();
      p.dataset.nodes = ns.map((n) => `${n.id}@${Math.round(n.x)},${Math.round(n.y)}`).join(" ");   // for tests: where each node landed
      p.dataset.groups = frames.map((f) => `${f.g.id}@${f.box.join(",")}`).join(" ");   // and each frame: left, top, right, bottom
      p.dataset.centre = p.centre ?? "";
      scope();
      const kinds = [...new Set(g.edges.map((e) => e.kind))].filter((k) => k !== "over" && k !== "parts");
      const how = "Klik: de buurt van een kaart; nog eens: naar de span."
        + " Terug: Alt ← of Terug van de browser. Sleep: alleen hier."
        + " Shift-klik kaarten: een groep.";
      foot.replaceChildren(...kinds.map((k) => {
        const c = button("", () => { offKinds.has(k) ? offKinds.delete(k) : offKinds.add(k); build(); foot.querySelector(`[data-kind="${k}"]`)?.focus(); }, "fpl-kchip");
        c.dataset.kind = k; c.ariaPressed = String(!offKinds.has(k));
        c.style.setProperty("--lc", edgeColour(k));
        c.innerHTML = `<svg width="16" height="10" aria-hidden="true">`
          + `<path class="fpl-edge" data-kind="${k}" d="M1 5H15"/></svg>`;
        if (k !== "code") c.append(ico(signOf(k)));
        c.append(kindName(k));
        return c;
      }), el("button", { type: "button", className: "fpl-why", title: how, ariaLabel: how, onclick: () => toast(how) }, ico("why")));
      select(p.centre, false);
      fade();   // the new cards as the query and the filter have them
    }
    /** Buurt or Hele pagina, the graph's reach; Buurt once it had a centre. */
    function scope() {
      const ways = [["hood", "Buurt"], ["page", "Hele pagina"]];
      head.replaceChildren(...ways.map(([k, name]) => {
        const b = button(name, () => p.go(k === "page" ? null : p.last));
        b.role = "radio"; b.dataset.scope = k;
        b.ariaChecked = String((k === "page") === !p.centre);
        b.disabled = k === "hood" && !p.last;
        return b;
      }));
    }
    /**
     * Stand round a node, or round none (the whole page), a step the
     * browser's Back and Alt ← walk back (push false: a step walked to).
     */
    p.go = (nid, push = true) => {
      p.centre = nid ?? null;
      if (nid) p.last = nid;
      if (push) history.pushState({ fplGraph: p.centre ?? "" }, "");
      if (p.view !== "graph") p.show("graph"); else build();
    };
    /**
     * A relation's sign (feedback 24): its own shape per kind, so the
     * kinds part without their colour, in a column of its own between
     * its ends and what it relates, off the cards; its word under the
     * mouse, in a pill above it.
     */
    function sign(n, r) {
      const word = kindName(r.labels[0]);
      const b = el("button", { type: "button", className: "fpl-node fpl-dia",
        ariaLabel: `${word}: ${clip(nodeText({ id: r.targets[0] }), 30)}` },
      ico(signOf(n.kind)));
      b.style.setProperty("--lc", edgeColour(n.kind));
      b.addEventListener("mouseenter", () => {
        const pill = el("span", { className: "fpl-pill" }, word);
        pill.style.left = `${n.x}px`;
        pill.style.top = `${n.y - SIGN / 2 - 12}px`;
        pill.style.setProperty("--lc", edgeColour(n.kind));
        area.append(pill);
      });
      b.addEventListener("mouseleave", () => {
        for (const x of area.querySelectorAll(".fpl-pill")) x.remove();
      });
      return b;
    }
    /**
     * Put each card and sign where its node is, and draw the edges along
     * the routes the layout gave them; a dragged card's edges run straight
     * to it, from border to border, until the next drawing.
     */
    function place2() {
      for (const f of frames) {   // round its cards where they stand, also while one is dragged
        const xs = f.ms.map((n) => n.x), ys = f.ms.map((n) => n.y);
        // 13px above the cards, so the tab on the frame's top edge stands clear of them
        f.box = [Math.min(...xs) - CW / 2 - 8, Math.min(...ys) - CH / 2 - 13, Math.max(...xs) + CW / 2 + 8, Math.max(...ys) + CH / 2 + 8].map(Math.round);
        Object.assign(f.el.style, { left: `${f.box[0]}px`, top: `${f.box[1]}px`, width: `${f.box[2] - f.box[0]}px`, height: `${f.box[3] - f.box[1]}px` });
      }
      for (const n of nodes) { n.el.style.left = `${n.x}px`; n.el.style.top = `${n.y}px`; }
      const rim = (n, dx, dy) => {   // where the line from a node's middle, along dx dy, leaves its card
        const hw = n.w / 2 + 1, hh = n.h / 2 + 1;
        const t = Math.min(hw / (Math.abs(dx) || 1e-9),
          hh / (Math.abs(dy) || 1e-9), 1);
        return [n.x + dx * t, n.y + dy * t];
      };
      for (const e of g.edges.filter((x) => x.path)) {
        let pts = e.pts;
        if (e.a.moved || e.b.moved) {
          const dx = e.b.x - e.a.x, dy = e.b.y - e.a.y;
          pts = [rim(e.a, dx, dy), rim(e.b, -dx, -dy)];
        }
        const d = pts.map(([x, y], i) =>
          `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`);
        e.path.setAttribute("d", d.join(""));
      }
    }
    /** A card is dragged in this view only; a press without a move is a click. */
    function grab(n) {
      let from = null, moved = false;
      n.el.onpointerdown = (ev) => { if (ev.button) return; from = [ev.clientX, ev.clientY, n.x, n.y]; moved = false; n.el.setPointerCapture(ev.pointerId); };
      n.el.onpointermove = (ev) => {
        if (!from) return;
        const dx = ev.clientX - from[0], dy = ev.clientY - from[1];
        if (!moved && Math.hypot(dx, dy) < 4) return;
        moved = n.moved = true; n.el.classList.add("is-lift");
        n.x = from[2] + dx; n.y = from[3] + dy;
        place2();
      };
      n.el.onpointerup = () => { from = null; n.el.classList.remove("is-lift"); };
      n.el.onclick = (ev) => {
        ev.stopPropagation();
        if (moved) { moved = false; return; }
        if (ev.shiftKey && !n.rel) { choose(n.id); return; }   // Shift chooses cards for a group (board V3a)
        if (n.id === p.centre) { jump(n); return; }   // the centre: to the text
        p.go(n.id);
        if (p.beside) jump(n, true);   // beside the page, the page follows
      };
      n.el.classList.toggle("is-picked", chosen.has(n.id));
      n.el.onmouseenter = () => { hot(n.id); light(n.id); };
      n.el.onmouseleave = () => { hot(null); light(sel); };
    }
    /**
     * A group's frame (board V3b): a rounded field behind its cards, on
     * its top edge a tab with its name and its role. Under the mouse its
     * members light, here and in the text; a click on the tab of a group
     * of ours opens it in the form, where the cards chosen join it.
     */
    function frameOf(f) {
      const role = roleOf(f.g);
      const tab = el("button", { type: "button", className: "fpl-gtab", title: groupName(f.g) },
        el("span", { className: "fpl-sq" }), el("span", { className: "fpl-gname" }, groupName(f.g)),
        role ? el("span", { className: "fpl-grole" }, role) : null);
      tab.onclick = (ev) => { ev.stopPropagation(); if (f.g.mine) form(f.g); else toast("Een groep uit de sidecar wijzig je met lit facts"); };
      f.el = el("div", { className: "fpl-gframe" }, tab);
      f.el.dataset.group = f.g.id;
      f.el.onmouseenter = () => lightGroup(f.g.id);
      f.el.onmouseleave = () => lightGroup(null);
      area.append(f.el);
      return f;
    }
    /** Shift-click: a card joins the choice, or leaves it; the form shows while any is chosen. */
    function choose(nid) {
      chosen.has(nid) ? chosen.delete(nid) : chosen.add(nid);
      for (const n of nodes) n.el.classList.toggle("is-picked", chosen.has(n.id));
      if (chosen.size && !sheet) form(null);   // an open form keeps what was typed in it, and the focus
      else if (!chosen.size && !sheet?.group) { sheet?.remove(); sheet = null; }
      sheet?.querySelector("input").focus({ preventScroll: true });   // the click took it to the card
    }
    /**
     * The group form (board V3a, without its sentences): a name, a role
     * of four, Annuleer and Groep maken. Enter in the name saves: a new
     * row group/<naam> of the cards chosen, or, for a name a group of ours
     * has, those cards join it; an open group of ours takes its new name
     * and role, and its Verwijder lets it go. Esc lets the choice go.
     */
    function form(gr) {
      sheet?.remove();
      const name = el("input", { type: "text", value: gr ? groupName(gr) : "", autocomplete: "off" });
      const roles = el("div", { className: "fpl-roles", role: "radiogroup", ariaLabel: "Rol" }, ...["", "claim", "bewijs", "tegen"].map((r) => {
        const b = button(r || "geen rol", () => { for (const x of roles.children) x.ariaChecked = String(x === b); });
        b.role = "radio"; b.ariaChecked = String(r === (gr ? roleOf(gr) : "")); b.dataset.role = r;
        return b;
      }));
      const go = el("button", { type: "submit", className: "fpl-go" }, gr ? "Bewaar " : "Groep maken ", el("kbd", {}, "↩"));
      const f = sheet = el("form", { className: "fpl-gform", ariaLabel: gr ? "Groep" : "Nieuwe groep" },
        el("p", { className: "fpl-gform-h" }, gr ? "Groep" : "Nieuwe groep"),
        el("label", {}, el("span", {}, "Naam"), name), el("div", {}, el("span", { className: "fpl-glabel" }, "Rol"), roles),
        el("div", { className: "fpl-bar fpl-keys" }, gr ? button("Verwijder", () => { save(gr, "delete"); done(); }, "fpl-danger") : null,
          el("span", { className: "fpl-space" }), button("Annuleer", () => done()), go));
      f.group = gr;
      const done = () => { chosen.clear(); f.remove(); sheet = null; draw(); };
      f.onsubmit = (ev) => {
        ev.preventDefault();
        const label = slug(name.value);
        if (!label) { toast("Een groep heeft een naam"); name.focus(); return; }
        const role = roles.querySelector('[aria-checked="true"]')?.dataset.role ?? "";
        const named = all.find((r) => isGroup(r) && r.labels[0] === `group/${label}` && r !== gr);
        if (named && !named.mine) { toast("Die naam heeft een groep uit de sidecar"); name.focus(); return; }
        if (`group/${label}` === TRAY && role) { toast("Gepakte zinnen hebben geen rol"); return; }
        const into = named ?? gr, keep = (into?.labels ?? []).filter((l) => /^order\//.test(l));
        const labels = [`group/${label}`, ...role ? [`role/${role}`] : [], ...keep];
        const targets = [...new Set([...into?.targets ?? [], ...gr && named ? gr.targets : [], ...chosen])];
        if (gr && named) save(gr, "delete");   // renamed onto a group of ours: the two are one
        save(into ?? {}, { note: name.value.trim(), labels, targets });
        toast(into ? "Groep bewaard" : "Groep gemaakt");
        done();
      };
      f.onkeydown = (ev) => { if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); done(); } };
      p.insertBefore(f, foot);
      name.focus({ preventScroll: true });
      name.select();
    }
    /**
     * The edges of a node drawn heavier, through a relation's sign to its
     * other ends; the words stay on the signs, under the mouse, never on
     * a card (feedback 24).
     */
    function light(nid) {
      for (const e of g.edges.filter((x) => x.path)) {
        const on = !!nid && (e.a.id === nid || e.b.id === nid || (e.a.rel && e.b.id !== nid && g.edges.some((f) => f.path && f.b === e.a && f.a.id === nid))
          || (e.b.rel && g.edges.some((f) => f.path && f.a === e.b && f.b.id === nid)));
        e.path.classList.toggle("is-hot", on);
      }
    }
    /** Select a node: it and its neighbours stand out, the rest dims; none, all show alike. */
    function select(nid, scroll = true) {
      sel = nodes.some((n) => n.id === nid) ? nid : null;
      const near = new Set(sel ? [sel] : []);
      for (let i = 0; i < 2; i++) for (const e of g.edges.filter((x) => x.path)) {   // through a diamond to the other end
        if (near.has(e.a.id) && (i === 0 || e.a.rel)) near.add(e.b.id);
        if (near.has(e.b.id) && (i === 0 || e.b.rel)) near.add(e.a.id);
      }
      p.classList.toggle("has-sel", !!sel);
      for (const n of nodes) { n.el.classList.toggle("is-sel", n.id === sel); n.el.classList.toggle("is-near", near.has(n.id)); }
      light(sel);
      if (sel && scroll) nodes.find((n) => n.id === sel).el.scrollIntoView({ block: "nearest", inline: "nearest" });
    }
    area.onclick = (ev) => { if (p.view === "graph" && (ev.target === area || ev.target.closest?.(".fpl-edges"))) select(null); };
    /**
     * The tree (boards V3c, V4c): the groups as an argument, read by
     * outline(). A block per group: a grip, its role, its name, the
     * weight of its step as five dots (a dot on a step without a row
     * writes one, supports for bewijs and attacks for tegen), and a line
     * per member whose click jumps to it, as a graph card does. A block
     * hangs from its parent by a line from the parent's foot, as thick as
     * the step's weight, with + or − where it arrives and the step itself
     * as a diamond, which an undercut's line leaves from; under the mouse
     * the line says its weight. Each child has a spine of its own, the
     * last one outermost, so no two lines cross. The grip drags a block
     * to another place (or Alt with ↑ ↓ moves it one), and the groups are
     * numbered order/1 on down as they then stand. At the foot the tray:
     * a knob dropped on it pulls its span, a sentence dragged from it onto
     * a block joins that group.
     */
    const IND = 72, tray = el("section", { className: "fpl-tray", ariaLabel: "Gepakte zinnen", hidden: true });
    let treeKey = "", order = [];   // the groups in the order shown, for a drag to rewrite
    function tree() {
      const key = `${area.clientWidth}`;
      if (treeKey === key && tree.of === all) return;
      treeKey = key; tree.of = all;
      const items = outline(), list = el("div", { className: "fpl-tree" });
      if (!items.length) {   // no group yet: one empty block and its one action, not a blank plane (QA, block 4)
        const make = button("", () => { p.show("graph"); toast("Shift-klik de kaarten van de groep"); }, "fpl-tmake");
        make.append(ico("group"), "Maak groep");
        area.replaceChildren(el("div", { className: "fpl-tree" }, el("section", { className: "fpl-tblock fpl-tempty" }, make)));
        fillTray();
        p.dataset.tree = "";
        return;
      }
      const sv = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      sv.classList.add("fpl-edges", "fpl-tlines");
      area.replaceChildren(list);
      list.append(sv, ...items.map(blockOf));
      order = items.filter((x) => x.g).map((x) => x.g);
      sv.setAttribute("width", list.scrollWidth); sv.setAttribute("height", list.scrollHeight);
      for (const x of items) if (x.parent || x.uc) wire(x, items, list, sv);
      fillTray();
      p.dataset.tree = items.map((x) => `${x.g?.id ?? x.uc.id}@${x.depth}${x.parent ? `<${x.parent}` : ""}`).join(" ");   // for tests
    }
    /** A group's block, or an undercut's. */
    function blockOf(x) {
      const g = x.g, u = x.uc, rel = g ? x.rel : u;
      const b = el("section", { className: `fpl-tblock${u ? " is-uc" : ""}` });
      b.style.marginLeft = `${x.depth * IND}px`;
      b.dataset.id = (g ?? u).id;
      if (g) b.dataset.group = g.id;
      x.el = b;
      const head = el("div", { className: "fpl-thead" });
      if (g) {
        const grip = el("button", { type: "button", className: "fpl-grip", ariaLabel: `Verplaats ${groupName(g)}`, title: g.mine ? "Sleep om te ordenen" : "Uit de sidecar" });
        grip.innerHTML = '<svg width="10" height="16" viewBox="0 0 10 16" aria-hidden="true"><g fill="currentColor"><circle cx="3" cy="3" r="1.3"/><circle cx="7" cy="3" r="1.3"/><circle cx="3" cy="8" r="1.3"/><circle cx="7" cy="8" r="1.3"/><circle cx="3" cy="13" r="1.3"/><circle cx="7" cy="13" r="1.3"/></g></svg>';
        reorder(grip, b, g);
        const role = roleOf(g);
        head.append(...[grip, role && el("span", { className: "fpl-trole" }, el("span", { className: "fpl-sq" }), role),
          el("span", { className: "fpl-tname" }, groupName(g))].filter(Boolean));
        b.onmouseenter = () => lightGroup(g.id);
        b.onmouseleave = () => lightGroup(null);
      } else head.append(el("span", { className: "fpl-tuc" }, "undercut"), el("span", { className: "fpl-tname" }, u.note || ""));
      if (x.kind || u) head.append(weigh(rel, rel ? null : (n) => save({}, { note: "", labels: [x.kind], targets: [g.id, x.parent], weight: n })));
      const ids = g ? g.targets : [u.targets[0]];
      b.append(head, el("ul", { className: "fpl-trows" }, ...ids.map((t) => {
        const r = all.find((y) => y.id === t), span = typeof r?.text === "string" || !!bundleOf(t);
        const sq = el("span", { className: `fpl-sq${span ? "" : " is-note"}` });
        if (span) sq.style.setProperty("--lc", tone(r ?? bundleOf(t)));
        const go = el("button", { type: "button", className: "fpl-trow", title: said(t) }, sq, el("span", {}, said(t)));
        go.dataset.id = t;
        go.onclick = (ev) => { ev.stopPropagation(); jump({ id: t }); };
        go.onmouseenter = () => hot(t);
        go.onmouseleave = () => hot(null);
        return el("li", {}, go);
      })));
      return b;
    }
    /**
     * The line from a parent's foot to a block: down its own spine, then
     * across to the block's head. The k-th of n children takes the spine
     * 8px further in than the one after it, so a longer line is further
     * out and none crosses another. An undercut's line leaves the diamond
     * of the step it attacks.
     */
    function wire(x, items, list, sv) {
      const box = (e) => ({ l: e.offsetLeft, t: e.offsetTop, b: e.offsetTop + e.offsetHeight });
      const c = box(x.el), arm = c.t + 21;
      let sx, y0;
      if (x.uc) { sx = x.on.dia; y0 = x.on.arm + 6; }
      else {
        const pa = items.find((y) => y.g?.id === x.parent), sibs = items.filter((y) => y.parent === x.parent && y.g);
        const k = sibs.indexOf(x), pb = box(pa.el);
        sx = pb.l + 8 + 8 * Math.min(sibs.length - 1 - k, 3); y0 = pb.b;
      }
      const rel = x.uc ?? x.rel, w = rel?.weight ?? 0, kind = x.uc ? "attacks" : x.kind;
      const d = `M${sx} ${y0}V${arm}H${c.l}`, ns = "http://www.w3.org/2000/svg";
      const line = sv.appendChild(document.createElementNS(ns, "path")), hit = sv.appendChild(document.createElementNS(ns, "path"));
      line.setAttribute("d", d); hit.setAttribute("d", d);
      line.setAttribute("class", "fpl-tline"); hit.setAttribute("class", "fpl-thit");
      line.dataset.id = (x.g ?? x.uc).id;
      line.style.setProperty("--lc", rel ? `var(--fpl-${kind})` : "var(--fpl-edge)");
      line.style.strokeWidth = w ? 0.5 + 0.75 * w : 1.25;   // board V4c: 2, 2.75, 3.5 for 2, 3, 4
      x.arm = arm;
      x.dia = c.l - IND + 42;   // where this step's diamond stands, should an undercut aim at it
      if (!rel) return;
      const sign = el("span", { className: "fpl-tsign", role: "img", ariaLabel: `${kindName(kind)}${w ? `, gewicht ${w}` : ""}` });
      sign.innerHTML = `<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M1.5 5h7${kind === "supports" ? "M5 1.5v7" : ""}"/></svg>`;
      sign.style.cssText = `--lc: var(--fpl-${kind}); left: ${c.l - 12}px; top: ${arm}px`;
      const tip = el("span", { className: "fpl-wtip", hidden: true }, String(w));
      tip.style.left = `${c.l - 12}px`; tip.style.top = `${arm + 14}px`;
      const on = (v) => { line.classList.toggle("is-hot", v); if (w) tip.hidden = !v; };
      for (const e of [hit, sign]) { e.onmouseenter = () => on(true); e.onmouseleave = () => on(false); }
      list.append(sign, tip);
      if (!x.uc) {
        const dia = el("span", { className: "fpl-tinf" });
        dia.style.cssText = `--lc: var(--fpl-${kind}); left: ${x.dia}px; top: ${arm}px`;
        dia.dataset.id = rel.id;
        list.append(dia);
      }
    }
    /**
     * A block dragged by its grip, or moved by Alt with ↑ ↓ on it: a
     * dashed slot keeps its place among the others, and where it is let go
     * the groups are numbered anew. A group of the sidecar keeps its place.
     */
    function reorder(grip, b, g) {
      grip.onkeydown = (ev) => {
        if (!ev.altKey || (ev.key !== "ArrowUp" && ev.key !== "ArrowDown")) return;
        ev.preventDefault(); ev.stopPropagation();
        const ids = order.map((y) => y.id), i = ids.indexOf(g.id), j = i + (ev.key === "ArrowUp" ? -1 : 1);
        if (j < 0 || j >= ids.length) return;
        ids.splice(i, 1); ids.splice(j, 0, g.id);
        renumber(ids) && requestAnimationFrame(() => area.querySelector(`.fpl-tblock[data-group="${CSS.escape(g.id)}"] .fpl-grip`)?.focus());
      };
      grip.onpointerdown = (ev) => {
        if (ev.button) return;
        if (!g.mine) { toast("Een groep uit de sidecar ordent lit facts"); return; }
        ev.preventDefault();
        grip.setPointerCapture(ev.pointerId);
        const list = b.parentElement, y0 = ev.clientY, top = b.offsetTop;
        const slot = el("div", { className: "fpl-tslot" });
        slot.style.height = `${b.offsetHeight}px`; slot.style.marginLeft = b.style.marginLeft;
        let moved = false;
        grip.onpointermove = (e) => {
          if (!moved && Math.abs(e.clientY - y0) < 4) return;
          if (!moved) {
            moved = true; b.before(slot); list.classList.add("is-moving");
            Object.assign(b.style, { position: "absolute", top: `${top}px`, width: `${b.offsetWidth}px` });
            b.classList.add("is-lift");
          }
          b.style.top = `${top + e.clientY - y0}px`;
          const mid = b.offsetTop + b.offsetHeight / 2;   // the slot goes before the first block whose middle is below the dragged one's
          const next = [...list.querySelectorAll(".fpl-tblock[data-group]")].find((o) => o !== b && o.offsetTop + o.offsetHeight / 2 > mid);
          next ? next.before(slot) : list.append(slot);
        };
        grip.onpointerup = grip.onpointercancel = (e) => {
          grip.onpointermove = grip.onpointerup = grip.onpointercancel = null;
          if (!moved) return;
          slot.replaceWith(b);
          b.classList.remove("is-lift"); b.style.position = b.style.top = b.style.width = "";
          list.classList.remove("is-moving");
          if (e.type === "pointercancel" || !renumber([...list.querySelectorAll(".fpl-tblock[data-group]")].map((o) => o.dataset.group))) { treeKey = ""; tree(); }
        };
      };
    }
    /** Write order/1 on down as the ids stand; false when nothing changed or a sidecar group would have to move. */
    function renumber(ids) {
      const gs = ids.map((id) => all.find((r) => r.id === id)), now = (r) => r.labels.find((l) => /^order\//.test(l));
      const moved = gs.filter((r, i) => now(r) !== `order/${i + 1}`);
      if (!moved.length) return false;
      if (moved.some((r) => !r.mine)) { toast("Een groep uit de sidecar houdt haar plaats: die ordent lit facts"); return false; }
      for (const r of moved) save(r, { labels: [...r.labels.filter((l) => !/^order\//.test(l)), `order/${gs.indexOf(r) + 1}`] });
      draw();
      return true;
    }
    /**
     * The tray of pulled sentences (board V3c): a pill per member, in the
     * colour of the tray's scope; a click jumps to it, a drag onto a block
     * puts it in that group and out of the tray.
     */
    function fillTray() {
      const g = all.find((r) => r.labels?.[0] === TRAY);
      const pills = (g?.targets ?? []).map((t) => {
        const c = el("button", { type: "button", className: "fpl-tpill", title: said(t) }, el("span", { className: "fpl-sq" }), el("span", {}, clip(said(t), 60)));
        c.dataset.id = t;
        let from = null, moved = false;
        c.onpointerdown = (ev) => { if (ev.button) return; from = [ev.clientX, ev.clientY]; moved = false; c.setPointerCapture(ev.pointerId); };
        c.onpointermove = (ev) => {
          if (!from || (!moved && Math.hypot(ev.clientX - from[0], ev.clientY - from[1]) < 4)) return;
          moved = true; c.classList.add("is-lift");
          c.style.transform = `translate(${ev.clientX - from[0]}px, ${ev.clientY - from[1]}px)`;
          for (const o of area.querySelectorAll(".fpl-tblock")) o.classList.remove("is-over");
          blockAt(ev.clientX, ev.clientY, c)?.classList.add("is-over");
        };
        c.onpointerup = (ev) => {
          if (!from) return;
          from = null;
          if (!moved) return;
          const o = blockAt(ev.clientX, ev.clientY, c);
          c.classList.remove("is-lift"); c.style.transform = "";
          o?.classList.remove("is-over");
          if (o) join(t, all.find((r) => r.id === o.dataset.group));
        };
        c.onclick = (ev) => { ev.stopPropagation(); if (moved) { moved = false; return; } jump({ id: t }); };
        return c;
      });
      tray.replaceChildren(el("h2", {}, el("span", { className: "fpl-sq" }), "Gepakte zinnen"), el("div", { className: "fpl-pills" }, ...pills));
    }
    /** The group block under a point, the pill dragged there aside. */
    const blockAt = (x, y, drag) => {
      drag.style.visibility = "hidden";
      const o = document.elementFromPoint(x, y)?.closest?.(".fpl-tblock[data-group]");
      drag.style.visibility = "";
      return o;
    };
    /** Measure the frame: beside the column where 320px are left for the plane, else a sheet over the page. */
    p.fit = () => {
      const was = p.beside;
      p.beside = innerWidth >= 24 + 740 + 24 + 320;
      if (p.beside !== was) slide(() => document.body.classList.toggle("fpl-beside", p.beside));
      p.classList.toggle("is-sheet", !p.beside);
      const shift = new DOMMatrix(getComputedStyle(body).transform).m41;   // where the column ends, not where its slide is now
      p.x = p.beside ? Math.round(body.getBoundingClientRect().right - shift) + 24 : 0;
      p.style.left = `${p.x}px`;
      p.style.top = p.beside ? "" : `${Math.max(0, bar.getBoundingClientRect().bottom)}px`;   // a sheet under the bar, whose Weergave closes it
      pulled(p.view === "boom");   // a draw wraps the marks anew
      build();
    };

    p.close = close;
    /** Turn the plane to a view: the graph and its chips, or the tree and its tray. */
    p.show = (v) => {
      if (p.view === v) return;
      p.letGo?.();
      p.view = v; built = ""; treeKey = "";
      p.classList.toggle("is-boom", v === "boom");
      p.ariaLabel = v === "boom" ? "Boom" : "Graph";
      foot.hidden = head.hidden = v === "boom"; tray.hidden = v !== "boom";
      drawView();
      pulled(v === "boom");
      if (p.isConnected) layout();   // the knobs come or go with the tree
    };
    p.group = (nid) => {   // Groepeer… in a card's menu: from the whole page
      if (p.centre || p.view !== "graph") p.go(null);
      if (!chosen.has(nid)) choose(nid);
    };
    p.letGo = () => { if (!chosen.size && !sheet) return false; chosen.clear(); sheet?.remove(); sheet = null; for (const n of nodes) n.el.classList.remove("is-picked"); return true; };
    p.tabIndex = -1;
    p.insertBefore(tray, foot);
    p.show(view);
    document.body.append(p);
    layout();   // fit, and the margin gives way
    if (push && view === "graph")
      history.pushState({ fplGraph: p.centre ?? "" }, "");
    p.focus({ preventScroll: true });
  }

  // the graph's steps in the browser's history (feedback 25): Back and
  // Forward walk them, Back past the first closes the plane, and a step
  // walked to after the plane closed opens it there
  addEventListener("popstate", (ev) => {
    const f = ev.state?.fplGraph;
    if (f === undefined) { if (plane?.view === "graph") plane.close(); return; }
    if (plane) plane.go(f || null, false);
    else graph(f || null, "graph", false);
  });

  /** Download this browser's rows as <stem>.annot.json. */
  function exportRows() {
    const blob = new Blob([JSON.stringify(local(), null, 1) + "\n"],
      { type: "application/json" });
    const a = el("a", { href: URL.createObjectURL(blob), download: `${stem}.annot.json` });
    a.click();
    URL.revokeObjectURL(a.href);
  }

  /** Merge a file of rows for this page into this browser's, by id. */
  function merge(text) {
    let got;
    try { got = JSON.parse(text); } catch (e) { toast(`Geen JSON: ${e.message}`); return; }
    if (!Array.isArray(got)) { toast("Geen lijst van rijen"); return; }
    const by = new Map(local().map((r) => [r.id, r]));
    let n = 0;
    for (const r of got) if (r && r.item === item && typeof r.id === "string") { by.set(r.id, r); n++; }
    keep([...by.values()]);
    toast(`${n} rijen ingelezen`);
    draw();
  }

  function toast(text) {
    const t = el("div", { className: "fpl-annot-ui fpl-toast" }, text);
    document.body.append(t);
    setTimeout(() => t.remove(), 1800);
  }

  /* ---- the editor ---- */

  /**
   * The editor of a row: what it is about on one line, the note, the six
   * labels most used as chips (and those the row has) plus a field for
   * one more, which completes from every label known; ⌘↩ saves, esc
   * closes.
   */
  function editor(row, onDone) {
    const on = new Set(row.labels ?? []);
    // Maps, not objects: a label may be any name, __proto__ and constructor too
    const used = new Map(), t = new Map(Object.entries(tally()));
    for (const r of all) for (const l of r.labels ?? []) used.set(l, (used.get(l) ?? 0) + 1);
    const rank = (l) => (used.get(l) ?? 0) + (Number(t.get(l)) || 0);
    const seen = [...new Set([...LABELS, ...used.keys(), ...t.keys()])]
      .map((l, i) => [l, i]).sort((a, b) => rank(b[0]) - rank(a[0]) || a[1] - b[1]).map(([l]) => l);   // by use, then seed order
    const note = el("textarea", { placeholder: "Notitie", value: row.note ?? "", rows: 2 });
    const chips = el("div", { className: "fpl-chips" });
    const more = el("input", { placeholder: "ander label…", autocomplete: "off", title: "Een label, of naam/sub" });
    const known = el("datalist", { id: `fpl-labels-${Date.now().toString(36)}` }, ...seen.map((l) => el("option", { value: l })));
    more.setAttribute("list", known.id);
    const render = () => chips.replaceChildren(
      ...[...new Set([...seen.slice(0, 6), ...on])].map((l) => {
        const b = chip(l, on.has(l) ? "is-on" : "");
        b.onclick = () => { on.has(l) ? on.delete(l) : on.add(l); render(); };
        b.tabIndex = 0;
        b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); b.onclick(); } };
        return b;
      }), more);
    render();
    const add = () => {
      const l = more.value.trim();
      if (!LABEL.test(l)) { toast("Een label is naam/scope/…: geen spatie, geen leeg stuk"); return; }
      on.add(l); more.value = ""; render(); more.focus();
    };
    more.onkeydown = (e) => { if (e.key === "Enter" && more.value.trim()) { e.preventDefault(); add(); } };
    more.oninput = (e) => { if (!e.inputType || e.inputType === "insertReplacementText") add(); };   // a pick from the list
    const keys = el("div", { className: "fpl-bar fpl-keys" },
      row.id ? button("Verwijder", () => onDone("delete")) : null,
      el("span", { className: "fpl-space" }),
      button("Annuleer", () => onDone(null)),
      el("button", { type: "submit", className: "fpl-go" }, "Bewaar ", el("kbd", {}, "⌘↩")));
    const t0 = row.targets?.[0] ?? "", parent = all.find((r) => r.id === t0);
    const about = typeof row.text === "string" ? row.text
      : parent ? `Reactie op ${t0}: ${(parent.note || parent.text || (parent.labels ?? []).join(" ")).replace(/\s+/g, " ").slice(0, 140)}`
      : `${t0}: ${document.getElementById(t0)?.textContent.replace(/\s+/g, " ").trim().slice(0, 140) ?? ""}`;
    const fast = typeof row.text !== "string" && !row.id && quick().length
      ? el("div", { className: "fpl-chips fpl-quick" }, el("small", {}, "snel"),
        ...quick().map((l) => { const b = chip(l, "is-on"); b.tabIndex = 0;
          b.onclick = () => onDone({ note: note.value.trim(), labels: [...new Set([l, ...on])] });
          b.onkeydown = (e) => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); e.stopPropagation(); b.onclick(); } };
          return b; }))
      : null;
    // el, not form.append: append writes a null kid (no quick chips yet) as the text "null"
    const head = el("div", { className: "fpl-head" }, el("span", { className: "fpl-dot" }), el("span", { className: "fpl-q", title: about }, about));
    const form = el("form", { className: "fpl-editor" }, head, fast, note, chips, known, keys);
    form.onsubmit = (ev) => { ev.preventDefault(); onDone({ note: note.value.trim(), labels: [...on] }); };
    form.onkeydown = (e) => {
      if (e.key === "Escape") { e.stopPropagation(); onDone(null); disarm(); }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) form.requestSubmit();
    };
    setTimeout(() => note.focus(), 0);
    return form;
  }

  /** Save the editor's result on a new row (no id) or one of ours. */
  function save(row, got) {
    const mine = local();
    if (got === "delete") { keep(mine.filter((r) => r.id !== row.id)); return; }
    const now = Date.now();
    const done = { ...row, ...got, updatedAt: now };
    delete done.mine;
    if (row.id) mine[mine.findIndex((r) => r.id === row.id)] = done;
    else mine.push({ id: `a-${now.toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      item, commit, by: by() || undefined, targets: [], ...done, createdAt: now });
    keep(mine);
    const l = layerOf(done), off = offLayers();
    if (off.delete(l)) { offLayers(off); toast(`Laag ${l} weer aan`); }
  }
  /** A save from the editor: what the reader typed or picked counts toward the ranking and the offer. */
  function typed(row, got) {
    save(row, got);
    if (got === "delete") return;
    const t = new Map(Object.entries(tally())), added = (got.labels ?? []).filter((x) => !(row.labels ?? []).includes(x));
    for (const x of added) t.set(x, (Number(t.get(x)) || 0) + 1);
    tally(Object.fromEntries(t));
    offer(added);
  }
  /**
   * Offer a label as a quick chip once three rows of the page carry it
   * (VIKI: the tool recognises a type, the user confirms it). The offer
   * stays until answered, one at a time; a yes and a no are both kept,
   * so a label is asked about until it has an answer, then never again.
   */
  function offer(labels) {
    if (document.querySelector(".fpl-offer")) return;
    const rowsNow = rows();
    const l = labels.find((x) => !quick().includes(x) && !declined().includes(x)
      && rowsNow.filter((r) => r.labels?.includes(x)).length >= 3);
    if (!l) return;
    const say = (yes) => { (yes ? quick : declined)([...(yes ? quick() : declined()), l]); box.remove(); if (yes) toast(`${l} is een snelchip`); };
    const box = el("div", { className: "fpl-annot-ui fpl-toast fpl-offer" }, `Drie keer ${l}: als snelchip op een adres?`,
      button("Ja", () => say(true)), button("Nee", () => say(false)));
    document.body.append(box);
  }

  /** Open the editor for a row, in its card or in a new card at the given height. */
  function edit(row, card, rect) {
    closeEditor();
    const done = (got) => { closeEditor(); if (got) { typed(row, got); draw(); } else layout(); };
    const form = editor(row, done);
    if (wide()) {
      const c = card ?? el("div", { className: "fpl-card mine fpl-editing" });
      c.classList.add("fpl-editing");
      c.replaceChildren(form);
      if (!card) {
        margin.append(c);
        const at = marksOf("draft").length ? reach("draft") : null;   // the selection, lit while written
        if (at) c.dataset.id = "draft";
        c.style.top = `${(at ? at.y - HEAD : rect.top + scrollY) - top0()}px`;
      }
      editing = c;
      makeRoom(c);
      drawLines();
    } else {
      pop.replaceChildren(form);
      pop.hidden = false;
      const r = rect ?? card.getBoundingClientRect();
      pop.style.top = `${scrollY + r.bottom + 8}px`;
      pop.style.left = `${Math.max(8, Math.min(scrollX + r.left, scrollX + innerWidth - pop.offsetWidth - 8))}px`;
      editing = pop;
    }
  }

  /**
   * The card being written is a card in the stack: it stands below the
   * cards above it, and those below move down out of its way, so it never
   * covers one and the order of the lines holds; layout puts them back.
   */
  function makeRoom(c) {
    const cards = [...margin.querySelectorAll(".fpl-card")].filter((o) => o !== c).sort((a, b) => a.offsetTop - b.offsetTop);
    const above = cards.filter((o) => o.offsetTop < c.offsetTop);
    c.style.top = `${Math.max(c.offsetTop, ...above.map((o) => o.offsetTop + o.offsetHeight + GAP))}px`;
    let floor = c.offsetTop + c.offsetHeight + GAP;
    for (const o of cards.filter((o) => !above.includes(o))) {
      const y = Math.max(o.offsetTop, floor);
      o.style.top = `${y}px`;
      floor = y + o.offsetHeight + GAP;
    }
    margin.style.minHeight = `${Math.max(parseFloat(margin.style.minHeight) || 0, floor)}px`;
  }

  let editing = null;
  const open = new Set();   // the spans whose card is open in the spans stand
  function closeEditor() {
    if (!editing) return;
    if (editing === pop) pop.hidden = true;
    else editing.remove();
    editing = null;
    const drafts = marksOf("draft");
    if (drafts.length) { for (const m of drafts) m.replaceWith(...m.childNodes); body.normalize(); }
  }

  /* ---- the margin: cards at the height of their span, lines between ---- */

  const margin = el("div", { className: "fpl-annot-ui fpl-margin" });
  const lines = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  lines.setAttribute("class", "fpl-annot-ui fpl-lines");
  /** A press on a knob: a click arms a pick, as l does; a drag (on touch, after HOLD) carries the knob to the other end. */
  lines.addEventListener("pointerdown", (ev) => {
    const k = ev.target.closest?.(".fpl-knob");
    if (!k || ev.button > 0) return;
    ev.preventDefault();   // no selection starts and no mouse events follow: pointerDone and the pick's click stay out
    if (mode() !== "kantlijn") { toast("Verbinden doe je in de stand Kantlijn (a)"); return; }
    if (picking) unpick();
    drag = { from: k.dataset.id, id: ev.pointerId, x: ev.clientX, y: ev.clientY, live: false, touch: ev.pointerType === "touch" };
    if (drag.touch) drag.timer = setTimeout(() => drag && !drag.moved && carry(), HOLD);
    for (const [t, f] of DRAG) addEventListener(t, f);
  });
  lines.addEventListener("contextmenu", (ev) => { if (ev.target.closest?.(".fpl-knob")) ev.preventDefault(); });   // a long press carries, it opens no menu
  // a touch on a knob is the knob's: the page does not pan under it (touch-action does not reach into an svg)
  lines.addEventListener("touchstart", (ev) => { if (ev.target.closest?.(".fpl-knob")) ev.preventDefault(); }, { passive: false });
  // a stretch by keys holds while its knob has the focus; the focus gone, it is put back
  lines.addEventListener("focusout", (ev) => {
    if (stretching?.keys && ev.target.closest?.(".fpl-knob")?.dataset.id === stretching.id) { dropStretch(); toast("Niet bewaard: teruggezet"); }
  });
  for (const [t, on] of [["pointerover", true], ["pointerout", false], ["focusin", true], ["focusout", false]])
    lines.addEventListener(t, (ev) => { const k = ev.target.closest?.(".fpl-knob"); if (k && !editing) hot(on ? k.dataset.id : null); });
  const pop = el("div", { className: "fpl-annot-ui fpl-pop", hidden: true });

  /** The margin's left edge, in the window: RAIL past the text column (main), wherever Quarto's own margin column starts. */
  const rail = () => body.getBoundingClientRect().right + RAIL;
  /** The margin's width: RIGHT from the window's edge, at most a CARD and the gutter's 28px. */
  const reserve = () => Math.min(document.documentElement.clientWidth - RIGHT - rail(), 28 + CARD);
  /** Cards stand in the margin while Quarto shows its column and a card there is NARROW or more; else they fold in. */
  const wide = () => !!column && column.offsetWidth > 120 && reserve() >= 28 + NARROW;
  const top0 = () => margin.getBoundingClientRect().top + scrollY;

  /** Lay every card out: the head, the lost rows, then one card per span in page order. */
  function layout() {
    closeEditor();
    drawBar();
    document.body.classList.toggle("fpl-numbered", mode() !== "lezen");
    // spans off: their marks stay as anchors (a chain's number, a tfa clause), unpainted; a layer alone dims the rest (board V4b)
    document.body.classList.toggle("fpl-nospans", mode() !== "lezen" && offLayers().has("span"));
    document.body.classList.toggle("fpl-solo", mode() !== "lezen" && !!alone());
    for (const c of body.querySelectorAll(".fpl-inline")) c.remove();
    scrunch();
    if (reading?.closest(".fpl-scrunched")) read(null);   // folded away: nothing to read or write on
    heat();
    lens();   // now as well as at the end: an early return below must not leave the lens of another stand
    margin.replaceChildren();
    lines.replaceChildren();
    unbar();
    margin.style.minHeight = "";
    if (plane) { plane.fit(); dock(); lens(); fade(); knobs(); return; }   // the plane stands where the margin was: no cards, no lines
    const full = mode() === "kantlijn";
    if (wide()) {
      column.classList.add("fpl-column");
      if (margin.parentElement !== column) column.append(margin);
      // the margin starts RAIL past the text, under the bar's left edge, and ends where the bar ends, past Quarto's narrow column
      margin.style.width = `${reserve()}px`;
      margin.style.marginLeft = `${rail() - column.getBoundingClientRect().left}px`;
      if (lines.parentElement !== document.body) document.body.append(lines);
    } else {
      column?.classList.remove("fpl-column");
      lines.remove();
      margin.style.width = margin.style.marginLeft = "";
      if (margin.parentElement !== body) body.prepend(margin);
    }
    if (mode() === "lezen") return;
    const y0 = wide() ? Math.max(0, bar.getBoundingClientRect().bottom + GAP - top0()) : 0;   // the first card clears the bar
    const heads = new Set();   // one card per address: its other rows are readings in it
    const spans = all.filter((r) => (typeof r.text === "string" || addressed(r) || orphan(r) || r.labels?.[0] === "parts") && shows(r) && passes(r) && (full || open.has(r.id)))
      .filter((r) => typeof r.text === "string" || r.labels?.[0] === "parts" ? !partsOf(r.id) : orphan(r) || (!heads.has(r.targets[0]) && heads.add(r.targets[0])));
    if (!spans.length) {
      if (!full || offLayers().has("span")) return;   // the how-to is for an empty margin, not for spans switched off
      const h = margin.appendChild(hint());
      if (wide()) h.style.top = `${y0 + 10}px`;   // board A: 22px under the bar's rule, where a card would stand 12px under it
      return;
    }
    const lost = spans.filter((r) => state[r.id] !== "vers" || orphan(r));
    // by the line each draws: a card's order is its line's, so no two lines cross
    const found = spans.map((r) => ({ r, at: reach(r.id) })).filter((x) => x.at).sort((a, b) => a.at.y - b.at.y);
    if (wide()) {
      let y = y0;
      for (const r of lost) {
        const c = cardOf(r);
        margin.append(c);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      const base = top0();
      for (const { r, at } of found) {   // at its line, its dot on it; pushed down only, by the card above
        const c = cardOf(r);
        margin.append(c);
        c.dataset.y = at.y;
        y = Math.max(at.y - base - HEAD, y);
        c.style.top = `${y}px`;
        y += c.offsetHeight + GAP;
      }
      margin.style.minHeight = `${y}px`;
      drawLines();
    } else {
      for (const r of lost) margin.append(cardOf(r));
      for (const { r, at: { m } } of found) {
        const c = cardOf(r);
        c.classList.add("fpl-inline");
        (m.closest("p, li, pre, h1, h2, h3, h4, td, th, blockquote") ?? m).after(c);
      }
    }
    lens();   // last: the cards placed inline move the clauses it measures
    fade();
    drawAim();
  }

  /**
   * Where a span meets the gutter, in page coordinates: y, the middle of
   * its last line, where its line leaves and its card's dot stands; top
   * and bottom, its first and last line; end and foot, the end of its
   * last line, where the knob sits on the underline; tail, the mark (or
   * element) that line ends in, a bundle's last piece; and long, a span
   * over three lines or more, which the gutter marks with a bar instead
   * of an underline on every line. A folded span is its band's.
   */
  function reach(id) {
    const ms = anchorsOf(id).map(seen);
    if (!ms.length) return null;
    const rs = ms.flatMap((m) => [...m.getClientRects()].map((r) => Object.assign(r, { m })));
    if (!rs.length) rs.push(Object.assign(ms[0].getBoundingClientRect(), { m: ms[0] }));
    const last = rs.reduce((a, r) => (r.bottom > a.bottom + 1 || (r.bottom > a.bottom - 1 && r.right > a.right) ? r : a));
    const top = Math.min(...rs.map((r) => r.top));
    const rows = rs.map((r) => r.bottom).sort((a, b) => a - b).filter((b, i, a) => !i || b - a[i - 1] > 4).length;
    return { m: ms[0], tail: last.m, y: last.bottom - Math.min(last.height, 24) / 2 + scrollY, top: top + scrollY, bottom: last.bottom + scrollY,
      end: last.right + scrollX, foot: last.bottom - 2 + scrollY, long: rows >= 3 || last.bottom - top > LONG && rs.length === 1 };
  }
  const unbar = () => { for (const m of body.querySelectorAll("mark.fpl-long")) m.classList.remove("fpl-long"); };
  const svg = (tag, attrs, id) => {
    const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    n.dataset.id = id;
    return lines.appendChild(n);
  };

  /**
   * A line from each span to its card, in the span's colour, all in the
   * gutter: a short stub at the text's edge at the span's last line, then
   * one curve to the card's dot. Every line has the same x geometry and
   * the cards stand in the order of their lines, pushed only down, so
   * the lines never cross and never run through the text. A long span
   * has its bar at the stub; the knob sits at the end of every saved span.
   */
  function drawLines() {
    const h = Math.max(document.documentElement.scrollHeight, body.getBoundingClientRect().bottom + scrollY);
    lines.setAttribute("width", document.documentElement.scrollWidth);
    lines.setAttribute("height", h);
    lines.replaceChildren();
    unbar();
    const gx = gutter();
    for (const c of margin.querySelectorAll(".fpl-card[data-id]")) {
      const id = c.dataset.id, at = reach(id);
      if (!at) continue;
      const cls = c.classList.contains("mine") ? "mine" : "", style = `--lc: ${c.style.getPropertyValue("--lc")}`;
      svg("path", { d: curve(at.y, c), class: `fpl-line ${cls}`, style }, id);
      if (at.long) {
        for (const m of anchorsOf(id)) if (m.matches("mark.fact")) m.classList.add("fpl-long");
        svg("rect", { x: gx - 1.25, y: at.top, width: 2.5, height: at.bottom - at.top, rx: 1.25, class: `fpl-stretch ${cls}`, style }, id);
      }
      if (id === "draft") continue;   // a selection being written has nothing to drag yet (board B)
      knobAt(id, at, cls, style);
    }
    drawAim();
    paintStretch();   // a layout in the middle of a stretch draws it again
  }
  /** The knob at the end of a span: the handle that connects, stretches and, into the tree, pulls or joins. */
  function knobAt(id, at, cls, style) {
    const knob = svg("circle", { cx: at.end + 3, cy: at.foot, r: 4, class: `fpl-knob ${cls}`, style, tabindex: 0, role: "button",
      "aria-label": `Bolletje van “${clip(said(id), 40)}”: sleep het naar een andere span, kaart of feit, of druk l; langs de tekst, of met Shift en de pijlen, rek je de span` }, id);
    knob.appendChild(document.createElementNS("http://www.w3.org/2000/svg", "title")).textContent = "Sleep naar een span, kaart of feit om te verbinden, of langs de tekst om te rekken";
  }
  /**
   * Beside the tree the text keeps its knobs, no lines and no cards
   * (board V3c): a span is carried from there to the tray or into a group.
   */
  function knobs() {
    if (!plane?.beside || plane.view !== "boom" || mode() !== "kantlijn") return;
    lines.setAttribute("width", document.documentElement.scrollWidth);
    lines.setAttribute("height", Math.max(document.documentElement.scrollHeight, body.getBoundingClientRect().bottom + scrollY));
    if (lines.parentElement !== document.body) document.body.append(lines);
    for (const r of all.filter((x) => (typeof x.text === "string" || x.labels?.[0] === "parts") && shows(x) && passes(x) && !partsOf(x.id))) {
      const at = reach(r.id);
      if (at) knobAt(r.id, at, r.mine ? "mine" : "", `--lc: ${tone(r)}`);
    }
    drawAim();
  }
  /** The line from a span's stub, at the height y of its last line, to the dot of its card c: the same x geometry for every line. */
  function curve(y, c) {
    const gx = gutter(), cr = c.getBoundingClientRect(), x2 = cr.left + scrollX - 1, y2 = cr.top + scrollY + HEAD, k = Math.max(0, x2 - gx - 6) / 2;
    return `M${gx},${y} h6 C${gx + 6 + k},${y} ${x2 - k},${y2} ${x2},${y2}`;
  }

  /** The span, card and line of one row light up together. */
  function hot(id) {
    if (link) id = link.from;   // while a connect is in flight its start stays lit, whatever the pointer passes
    const group = new Set(id ? groupOf(id) : []);   // a piece lights its whole, the whole its pieces
    for (const n of [...body.querySelectorAll("mark.fact, .is-hot"), ...margin.querySelectorAll(".fpl-card"), ...lines.children,
      ...(plane?.querySelectorAll(".fpl-node") ?? [])])
      n.classList.toggle("is-hot", group.has(n.dataset.id));
    if (id) for (const e of anchorsOf(id)) if (!e.matches("mark.fact")) e.classList.add("is-hot");
    for (const n of body.querySelectorAll(".fpl-coref")) n.classList.remove("fpl-coref");
    if (id) for (const t of corefOf(id)) for (const e of [...marksOf(t), document.getElementById(t)])
      if (e && body.contains(e)) e.classList.add("fpl-coref");
  }
  /** The other ids a coref row (in a shown layer) groups with an id. */
  function corefOf(id) {   // the whole chain: sets sharing a member are one referent
    const sets = all.filter((r) => r.labels?.[0] === "coref" && shows(r) && Array.isArray(r.targets));
    const got = new Set([id]);
    for (let grew = true; grew;) {
      grew = false;
      for (const r of sets) if (r.targets.some((t) => got.has(t)))
        for (const t of r.targets) if (!got.has(t)) { got.add(t); grew = true; }
    }
    got.delete(id);
    return got;
  }

  /* ---- the tfa lens: t, c, f on clauses, and the resumes arcs ---- */

  const TFA = ["tfa/t", "tfa/c", "tfa/f"];
  /** Mark each clause with its value and draw the arcs; nothing in Lezen or with the tfa layer off. */
  /**
   * The coref chains in the layers shown: sets that share a member are
   * one chain (union-find), each chain its members in page order, the
   * chains numbered by where their first member stands.
   */
  function chains() {
    const up = new Map(), find = (x) => { while (up.get(x) !== x) { up.set(x, up.get(up.get(x))); x = up.get(x); } return x; };
    for (const r of all.filter((x) => x.labels?.[0] === "coref" && shows(x) && Array.isArray(x.targets)))
      for (const t of r.targets) { if (!up.has(t)) up.set(t, t); up.set(find(t), find(r.targets[0])); }
    const groups = new Map();
    for (const x of up.keys()) groups.set(find(x), [...(groups.get(find(x)) ?? []), x]);
    const at = (id) => anchorsOf(id)[0] ?? place(id);   // page order is document order; a member not on the page goes last
    const order = (a, b) => {
      const x = at(a), y = at(b);
      if (!x || !y) return !x - !y;
      return x === y ? 0 : x.compareDocumentPosition(y) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    };
    return [...groups.values()].map((g) => g.sort(order)).sort((a, b) => order(a[0], b[0]));
  }
  /** Number each member of each chain on the page; off in Lezen or with the coref layer off. */
  function chainMarks() {
    for (const e of body.querySelectorAll(".fpl-chain")) e.remove();
    if (mode() === "lezen" || offLayers().has("coref")) return;
    const got = new Map();   // element -> its chain numbers
    chains().forEach((g, i) => {
      for (const id of g) {
        const e = anchorsOf(id).at(-1) ?? place(id);   // a span split in marks, a whole of pieces, an address: its last anchor
        if (e && body.contains(e)) got.set(e, [...(got.get(e) ?? []), i + 1]);
      }
    });
    // a number of its own (fpl-annot-ui: no text of the page), so no pseudo-element of the page is taken over
    for (const [e, ns] of got) {
      const sup = el("sup", { className: "fpl-annot-ui fpl-chain" }, ns.join(","));
      e.matches(".fpl-p") ? e.append(sup) : e.after(sup);
    }
  }
  function lens() {
    chainMarks();
    for (const e of body.querySelectorAll("[data-tfa]")) { delete e.dataset.tfa; delete e.dataset.tfaRow; }
    document.querySelector(".fpl-arcs")?.remove();
    if (mode() === "lezen") return;
    for (const r of all.filter(shows)) {
      const v = TFA.includes(r.labels?.[0]) && r.labels[0], e = v && document.getElementById(r.targets?.[0]);
      if (e && body.contains(e)) { e.dataset.tfa = v.slice(4); e.dataset.tfaRow = r.id; }
    }
    const arcs = all.filter((r) => r.labels?.[0] === "resumes" && r.targets?.length === 2 && shows(r))
      .map((r) => [r, ...r.targets.map((t) => document.getElementById(t))])
      .filter(([, a, b]) => a && b && body.contains(a) && body.contains(b) && seen(a) !== seen(b));   // one band: no arc
    if (!arcs.length) return;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.classList.add("fpl-arcs");
    const H = document.documentElement.scrollHeight;
    svg.setAttribute("width", "100%"); svg.setAttribute("height", H);
    // in the gutter left of the text, however narrow (feedback 20: with the graph open the column stands at x 24)
    const left = Math.max(body.getBoundingClientRect().left + scrollX - 8, 10);
    for (const [r, a, b] of arcs) {
      const [ya, yb] = [a, b].map((e) => { const r = seen(e).getBoundingClientRect(); return r.top + scrollY + r.height / 2; });
      const bow = Math.min(40, 8 + Math.abs(ya - yb) / 12, (left - 4) * 4 / 3);   // a cubic's controls at left - bow reach 3/4 of it
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", `M ${left} ${ya} C ${left - bow} ${ya}, ${left - bow} ${yb}, ${left} ${yb}`);
      path.dataset.id = r.id;
      path.append(Object.assign(document.createElementNS("http://www.w3.org/2000/svg", "title"),
        { textContent: `${r.targets[0]} resumes ${r.targets[1]}${r.mine ? " (klik: weg)" : ""}` }));
      if (r.mine) path.onclick = () => { keep(local().filter((x) => x.id !== r.id)); draw(); toast(`${r.id} weg`); };
      svg.append(path);
    }
    document.body.append(svg);
  }
  /** Alt-click a clause: its value goes t, c, f, none; one row of this browser per clause holds it. */
  function cycle(id) {
    const marks = (r) => r.targets?.[0] === id && TFA.includes(r.labels?.[0]);
    const mine = local(), at = mine.findIndex(marks);
    const filed = sidecar.some(marks);   // the sidecar's value is cleared there, not here
    const cur = [...all].reverse().find(marks)?.labels[0] ?? null;
    const next = TFA[(TFA.indexOf(cur) + 1)] ?? (filed ? TFA[0] : null);
    if (at >= 0) mine.splice(at, 1);
    keep(mine);
    if (next) save({ targets: [id] }, { note: "", labels: [next] });
    draw();
    toast(next ? `${id}: ${next}` : `${id}: geen tfa`);
  }

  /* ---- bands: blocks folded into a seam, the page one scroll ---- */

  const SCRUNCH = "fpl-annot:scrunch:" + item;
  /**
   * The bands, oldest first, each the ids of its first and last block:
   * the URL's ?scrunch= when it has one, else this browser's for the page
   * (a single id is a band of one block). scrunch() keeps it settled:
   * resolved, each pair in page order, no two overlapping.
   */
  let bands = (() => {
    let s = new URLSearchParams(location.search).get("scrunch");
    if (s == null) try { s = localStorage.getItem(SCRUNCH); } catch { /* no storage */ }
    return (s || "").split(",").filter(Boolean).map((p) => { const [a, b = a] = p.split(".."); return [a, b]; });
  })();

  /** The addressed blocks (essay.lua's fpl-p), in page order: a band's ends are two of them. */
  const units = () => [...body.querySelectorAll(".fpl-p")];
  /** Every block of the page, addressed or not (headings, lists, tables), in page order. */
  const leaves = () => [...body.querySelectorAll(":scope > *, section > *")]
    .filter((e) => !e.matches("section, script, style, .fpl-annot-ui, .fpl-card"));
  /** The band a folded element is in, or null; seen() is where an element shows. */
  const bandOf = (e) => {
    const l = e.closest(".fpl-scrunched");
    return l && body.querySelector(`.fpl-band[data-k="${l.dataset.band}"]`);
  };
  const seen = (e) => bandOf(e) ?? e;
  /** A block's address as the page numbers it: 1.2.1.3 §4, or §5:C for code. */
  const addr = (u) => `${u.dataset.addr ?? ""} §${u.dataset.n}${u.dataset.kind === "C" ? ":C" : ""}`.trim();

  /** The bands as [first, last] indices into us; unresolved ones dropped, one overlapped merged into the later. */
  function settle(us) {
    const out = [];
    for (const ends of bands) {
      let [i, j] = ends.map((id) => us.indexOf(document.getElementById(id)?.closest(".fpl-p"))).sort((x, y) => x - y);
      if (i < 0) continue;
      for (let k = out.length - 1; k >= 0; k--) {
        const [p, q] = out[k];
        if (p <= j && i <= q) { i = Math.min(i, p); j = Math.max(j, q); out.splice(k, 1); }
      }
      out.push([i, j]);
    }
    return out;
  }

  /**
   * Draw the bands (board G, feedback 3). Every element from a band's
   * first block to its last is hidden (fpl-scrunched, data-band = the
   * band's index) and a seam stands before the first of them: a button
   * of SEAM pixels, two hairlines across the column and at their left
   * its range, "1.2.1.3 §9 – 1.2.1.4 §7 · 25 blokken". However much it
   * folds, a seam is that high, so a fold never leaves a field of lines
   * to read and both ends of a long jump fit in one view. A click (or
   * Enter) opens it; under the mouse or the focus it darkens and a tip
   * under it says how to fold further, and nothing moves.
   */
  function scrunch() {
    for (const b of body.querySelectorAll(".fpl-band")) b.remove();
    const us = units(), ls = leaves(), got = settle(us);
    bands = got.map(([i, j]) => [us[i].id, us[j].id]);
    for (const l of ls) l.classList.remove("fpl-scrunched");
    got.forEach(([i, j], k) => {
      const fold = ls.slice(ls.indexOf(us[i]), ls.indexOf(us[j]) + 1);
      const n = j - i + 1, to = j > i ? ` – ${addr(us[j])}` : "";
      const range = `${addr(us[i])}${to} · ${n} blok${n > 1 ? "ken" : ""}`;
      const seam = el("button", {
        type: "button", className: "fpl-annot-ui fpl-band",
        ariaExpanded: "false",
        ariaLabel: `Ingevouwen: ${range}. Klik om te openen.`,
        onclick: () => setBands(bands.filter((_, x) => x !== k)) },
      el("span", { className: "fpl-seam" }, ico("shift"), range),
      el("span", { className: "fpl-tip", ariaHidden: "true" },
        "Klik opent · ", el("kbd", {}, "Shift"),
        " + scroll boven de tekst vouwt verder, terug scrollen opent"));
      Object.assign(seam.dataset, { k, range });
      for (const l of fold) { l.classList.add("fpl-scrunched"); l.dataset.band = k; }
      fold[0].before(seam);
    });
  }

  /** Write the bands to the URL (?scrunch=a..b,c..d, kept readable) and to this browser. */
  function persist() {
    const s = bands.map(([a, b]) => (a === b ? a : `${a}..${b}`)).join(","), u = new URL(location.href);
    if (s) u.searchParams.set("scrunch", s); else u.searchParams.delete("scrunch");
    u.search = u.search.replace(/%2[CF]/gi, decodeURIComponent);
    history.replaceState(history.state, "", u);
    try { if (s) localStorage.setItem(SCRUNCH, s); else localStorage.removeItem(SCRUNCH); } catch { /* no storage */ }
  }
  /** Take a new list of bands: lay the page out with them, then keep them. */
  function setBands(list) { bands = list; layout(); persist(); }

  /** Where an id shows on the page: a row's span, else the element with that id; null when neither. */
  const place = (id) => {
    const e = anchorsOf(id)[0] ?? document.getElementById(id);
    return e && body.contains(e) ? e : null;
  };
  /**
   * Toon beide: fold every block between a row's span and another place
   * into a band, so both are in view. A band over either end opens, also
   * when nothing lies between to fold; bands between the two join the
   * new one (settle).
   */
  function both(from, to) {
    const us = units();
    const [i, j] = [from, to].map((id) => us.indexOf(place(id)?.closest(".fpl-p"))).sort((x, y) => x - y);
    if (i < 0) { toast("Niet op deze pagina"); return; }
    const covers = (b, x) => { const [p, q] = b.map((id) => us.indexOf(document.getElementById(id))); return p <= x && x <= q; };
    const kept = bands.filter((b) => !covers(b, i) && !covers(b, j));
    const fold = j - i >= 2 ? [[us[i + 1].id, us[j - 1].id]] : [];
    if (!fold.length && kept.length === bands.length) { toast("Ze staan al samen in beeld"); return; }
    setBands([...kept, ...fold]);
    (fold.length ? bandOf(us[i + 1]) : us[i]).scrollIntoView({ block: "center", behavior: "smooth" });
  }

  /**
   * Vouw tot de spans, in the menu (LiquidText's merged highlights): fold
   * every run of blocks further than context blocks from a span the filter
   * lets through and the query finds, so those spans stand together with
   * their surroundings. Chosen again while the bands are just that, it
   * opens them all; a new context refolds them at once.
   */
  const CONTEXT = "fpl-annot:context";
  let context = (() => { try { const n = localStorage.getItem(CONTEXT); return n != null && /^[0-3]$/.test(n) ? +n : 1; } catch { return 1; } })();
  /**
   * The runs of blocks further than n blocks from a drawn span the query
   * did not fade, as bands; null when no such span is drawn.
   */
  function runsNear(n) {
    const us = units(), near = new Set();
    for (const m of body.querySelectorAll("mark.fact:not(.fpl-faded)")) {
      const i = us.indexOf(m.closest(".fpl-p"));
      if (i >= 0) for (let t = i - n; t <= i + n; t++) near.add(t);
    }
    if (!near.size) return null;
    const runs = [];
    for (let i = 0; i < us.length; i++)
      if (!near.has(i)) { const a = i; while (i + 1 < us.length && !near.has(i + 1)) i++; runs.push([us[a].id, us[i].id]); }
    return runs;
  }
  /** Whether a list of bands (the bands now, by default) is just these runs. */
  const folded = (runs, list = bands) => !!runs && runs.length === list.length
    && runs.every(([a, b], x) => a === list[x][0] && b === list[x][1]);
  const NOSPAN = () => (mode() === "lezen"
    ? "Lezen onderstreept niets: kies Spans of Kantlijn"
    : "Geen span in beeld om tot te vouwen");
  function squeeze() {
    const runs = runsNear(context);
    if (!runs) { toast(NOSPAN()); return; }
    const same = folded(runs);
    setBands(same ? [] : runs);
    if (same) toast("Alles open");
  }
  function setContext(n) {
    const was = folded(runsNear(context));
    context = n;
    try { localStorage.setItem(CONTEXT, n); } catch { /* no storage */ }
    if (was) setBands(runsNear(n));
  }

  /**
   * The fold of a gesture, from the moment it began (g) and how far it has
   * gone (s, pixels; less than 0 back). On: g.base with the blocks around
   * g.mid folded, the block itself first and then one more a side by
   * turns, as many as s covers of their heights g.h (a block already
   * folded costs nothing, so a fold grows through a band), none at or
   * past the bounds g.i and g.j. Back past OPEN: g.base without the bands
   * g.open. A pinch and a Shift+wheel both fold so.
   */
  const OPEN = 40;
  function fold(g, s) {
    if (s < -OPEN && g.open.length)
      return g.base.filter((b) => !g.open.includes(b));
    if (s <= 0 || g.mid < 0) return g.base;
    const { us, h, i, j } = g;
    let a = g.mid, b = a - 1, sum = 0;   // [a, b], empty, grows by turns
    const fits = (t) => t > i && t < j && sum + h[t] <= s;
    for (let left = false; ; left = !left) {
      const t = left ? a - 1 : b + 1;
      if (fits(t)) { sum += h[t]; left ? a-- : b++; }
      else if (!fits(left ? b + 1 : a - 1)) break;
    }
    return a <= b ? [...g.base, [us[a].id, us[b].id]] : g.base;
  }
  /**
   * What folding each block takes away as the page shows now: down to the
   * next block shown, headings and tables between included; 0 when folded.
   */
  function heights(us) {
    const r = us.map((u) => (u.classList.contains("fpl-scrunched")
      ? null : u.getBoundingClientRect()));
    return r.map((x, t) => {
      const n = r.findIndex((y, u) => u > t && y);
      return !x ? 0 : n < 0 ? x.height : Math.max(0, r[n].top - x.top);
    });
  }
  /** The first block shown whose bottom is at or below window y, or -1. */
  const blockAt = (us, y) => us.findIndex((u) =>
    !u.classList.contains("fpl-scrunched")
    && u.getBoundingClientRect().bottom >= y);

  /**
   * Pinch (the paper's gesture): two fingers on the text, drawn together,
   * fold the blocks between them from the middle outward, as many whole
   * blocks as the fingers have closed by; drawn apart over a band, they
   * open it. The fold shows while the fingers move and is kept when they
   * lift. Only a two-finger move is cancelled, so one finger still
   * scrolls, and the page does not zoom under a pinch.
   */
  let pinch = null;
  const ys = (ts) => [...ts].map((t) => t.clientY).sort((a, b) => a - b);
  function pinchMove(ev) {
    if (!pinch || ev.touches.length !== 2) return;
    ev.preventDefault();
    const [y0, y1] = ys(ev.touches), next = fold(pinch, pinch.d0 - (y1 - y0));
    const key = JSON.stringify(next);
    if (key !== pinch.key) { pinch.key = key; bands = next; layout(); }
  }
  function pinchEnd(ev) {
    if (!pinch || ev.touches.length > 1) return;
    for (const x of pinch.at) for (const [t, f] of PINCH) x.removeEventListener(t, f);
    if (pinch.key) persist();
    pinch = null;
  }
  /** On the elements the fingers came down on: a band is drawn anew under them, and an event on a detached element never reaches body. */
  const PINCH = [["touchmove", pinchMove], ["touchend", pinchEnd], ["touchcancel", pinchEnd]];
  body.addEventListener("touchstart", (ev) => {
    if (pinch) pinchEnd({ touches: [] });
    if (ev.touches.length !== 2 || [...ev.touches].some((t) => t.target.closest?.(".fpl-card, .fpl-topbar, .fpl-menu"))) return;
    const [y0, y1] = ys(ev.touches), us = units();
    const i = blockAt(us, y0), j1 = blockAt(us, y1);
    const j = j1 < 0 ? us.length : j1;
    const between = [...body.querySelectorAll(".fpl-band")].filter((b) => { const r = b.getBoundingClientRect(); return r.bottom >= y0 && r.top <= y1; });
    // i < 0: the fingers are below the last block
    const mid = i >= 0 && j - i > 1 ? Math.floor((i + j) / 2) : -1;
    pinch = { d0: y1 - y0, base: bands, us, i, j, mid, h: heights(us),
      open: between.map((b) => bands[+b.dataset.k]), key: "", at: new Set([...ev.touches].map((t) => t.target)) };
    for (const x of pinch.at) for (const [t, f] of PINCH) x.addEventListener(t, f, { passive: false });
  }, { passive: true });

  /**
   * Shift+wheel over the text, LiquidText's gesture at a desk (board G,
   * feedback 3): turned on, the wheel folds the blocks around the pointer,
   * the block under it first (fold), as far as it has turned; turned back
   * past OPEN, it opens the band under the pointer, else the nearest one
   * in the window. With a filter or a query on, the same turn folds to
   * the spans they let through, at the menu's Context (Vouw tot de spans),
   * and back opens what that folded. The fold shows while the wheel turns,
   * what was under the pointer stays under it, and IDLE ms without a turn
   * keep it (the URL and this browser). macOS sends a Shift+wheel as a
   * sideways turn, so the larger delta counts; Shift+wheel over a wide
   * code block folds rather than scrolls it, a sideways swipe still does.
   * A turn that can do nothing says why, once.
   */
  const IDLE = 250;
  let wheel = null;
  const filtering = () => !!found || hidden().size + offLayers().size > 0;
  /** A wheel gesture begins at window height y: what it folds from. */
  function wheelStart(y) {
    const us = units(), seams = [...body.querySelectorAll(".fpl-band")];
    const box = (b) => b.getBoundingClientRect();
    const dist = (b) => Math.max(0, box(b).top - y, y - box(b).bottom);
    const near = seams
      .filter((b) => box(b).bottom > 0 && box(b).top < innerHeight)
      .sort((a, b) => dist(a) - dist(b))[0];
    const over = near && dist(near) === 0 ? bands[+near.dataset.k] : null;
    const mid = over
      ? us.indexOf(document.getElementById(over[0])) : blockAt(us, y);
    return { base: bands, us, i: -1, j: us.length, mid, h: heights(us),
      s: 0, key: JSON.stringify(bands), said: false,
      open: near ? [bands[+near.dataset.k]] : [],
      runs: filtering() ? runsNear(context) : undefined };
  }
  /** The bands a wheel gesture asks for now, or a reason it can do nothing. */
  function wheelFold(g) {
    const to = g.runs !== undefined;   // a filter or a query: to its spans
    if (to && g.s > OPEN) return g.runs ?? NOSPAN();
    if (to && g.s < -OPEN && folded(g.runs, g.base)) return [];
    if (to && g.s > 0) return g.base;
    if (g.s > 0 && g.mid < 0)
      return "Onder het laatste blok valt niets te vouwen";
    if (g.s < -OPEN && !g.open.length) return "Geen band in beeld om te openen";
    return fold(g, g.s);
  }
  function wheelEnd() {
    if (wheel && wheel.key !== JSON.stringify(wheel.base)) persist();
    wheel = null;
  }
  body.addEventListener("wheel", (ev) => {
    if (!ev.shiftKey || ev.ctrlKey || ev.metaKey) return;
    if (ev.target.closest?.(".fpl-card, .fpl-inline")) return;
    ev.preventDefault();
    const d = Math.abs(ev.deltaX) > Math.abs(ev.deltaY) ? ev.deltaX : ev.deltaY;
    wheel ??= wheelStart(ev.clientY);
    clearTimeout(wheel.t);
    wheel.t = setTimeout(wheelEnd, IDLE);
    wheel.s += d * [1, 16, innerHeight][ev.deltaMode];   // pixels, lines, pages
    const next = wheelFold(wheel);
    if (typeof next === "string") {   // nothing to do: why, once a gesture
      if (!wheel.said) toast(next);
      wheel.said = true;
      return;
    }
    const key = JSON.stringify(next);
    if (key === wheel.key) return;
    // what was under the pointer stays under it: the block it folds from
    const at = wheel.us[wheel.mid];
    const y = at && seen(at).getBoundingClientRect().top;
    wheel.key = key;
    bands = next;
    layout();
    if (at) scrollBy(0, seen(at).getBoundingClientRect().top - y);
  }, { passive: false });

  /* ---- density: how many rows each block carries, in its gutter ---- */

  /** The row a thread hangs from: a fact or reply followed up its first target to a span's or an address's row. */
  function trunk(r, been = new Set()) {
    const up = typeof r.text !== "string" && all.find((x) => x.id === r.targets?.[0]);
    return up && !been.has(r.id) ? trunk(up, been.add(r.id)) : r;
  }

  /**
   * Shade each block's gutter bar by the rows that hang from it: a span's
   * row, the facts about it and their replies, all depths, of the threads
   * whose root the filter lets through (as layout draws them). A folded block counts toward its band's
   * bar. The three greys are cut at the terciles of the page's non-zero
   * block counts, so a shade ranks a block against this page, not against
   * a fixed scale; a band's sum may pass the top cut and is then darkest.
   * Off in Lezen, which shows nothing.
   */
  function heat() {
    for (const h of body.querySelectorAll(".fpl-heat")) h.remove();
    if (mode() === "lezen") return;
    const per = new Map();
    for (const r of all) {
      const t = trunk(r), b = shows(r) && layerOf(r) !== "tfa" && passes(t) && anchorsOf(t.id)[0]?.closest(".fpl-p");   // passes: as the stand draws it
      if (b) per.set(b, (per.get(b) ?? 0) + 1);
    }
    const c = [...per.values()].sort((x, y) => x - y), cut = (q) => c[Math.ceil(q * c.length) - 1];
    const [t1, t2] = [cut(1 / 3), cut(2 / 3)], where = new Map();
    for (const [b, n] of per) where.set(seen(b), (where.get(seen(b)) ?? 0) + n);
    for (const [at, n] of where) {
      const bar = el("span", { className: "fpl-annot-ui fpl-heat", title: `${n} ${n === 1 ? "rij" : "rijen"}` });
      bar.dataset.level = n <= t1 ? 1 : n <= t2 ? 2 : 3;
      at.prepend(bar);
    }
  }

  /* ---- close reading: a cursor on one sentence, moved by keystroke ---- */

  let reading = null;   // the sentence the cursor is on (fpl-here), or null
  /**
   * Put the cursor on a sentence, or take it away (null); the hash names
   * it. The page scrolls only when the sentence has left the window (or
   * slid under a fixed bar at its top, EDGE pixels), and then brings it to
   * the middle, so the next steps read on without scrolling.
   */
  const EDGE = 64;
  function read(s) {
    mark(s);
    history.replaceState(history.state, "", s ? `#${s.id}` : location.pathname + location.search);
    const r = s?.getBoundingClientRect();
    if (r && (r.top < EDGE || r.bottom > innerHeight)) s.scrollIntoView({ block: "center" });
  }
  /** The cursor alone moved, hash and scroll left as they are. */
  function mark(s) {
    reading?.classList.remove("fpl-here");
    reading = s;
    s?.classList.add("fpl-here");
  }
  /**
   * The cursor follows the hash wherever it changes: at load, on in-page
   * navigation (hashchange), after a click on a number (replaceState,
   * which fires nothing). A hash that is not a showing sentence takes the
   * cursor away and stays.
   */
  function sync() {
    const e = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    mark(e?.matches(".fpl-s") && !e.closest(".fpl-scrunched") ? e : null);
  }
  addEventListener("hashchange", sync);
  /**
   * The cursor to the next (d = 1) or previous (d = -1) sentence that
   * shows: folded ones are passed over, so a band is jumped. Without a
   * cursor (or with one in a fold) it starts at the first sentence in view.
   */
  function step(d) {
    const ss = [...body.querySelectorAll(".fpl-s")].filter((s) => !s.closest(".fpl-scrunched"));
    const i = ss.indexOf(reading);
    if (i < 0) read(ss.find((s) => s.getBoundingClientRect().bottom > 0) ?? ss.at(-1) ?? null);
    else read(ss[Math.max(0, Math.min(ss.length - 1, i + d))]);
  }

  /* ---- selecting and clicking ---- */

  /** The shown index of a range's first character and past its last. */
  function bounds(ix, range) {
    const first = (after) => {
      let lo = 0, hi = ix.from.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1, [n, o] = ix.from[mid];
        if (range.comparePoint(n, o) >= after) hi = mid; else lo = mid + 1;
      }
      return lo;
    };
    let s = first(0), e = first(1);
    while (s < e && ix.flat[s] === " ") s++;
    while (e > s && ix.flat[e - 1] === " ") e--;
    return [s, e];
  }

  /** A selection in the body opens the editor for a new quote row; a click on a mark lights or edits it. */
  function pointerDone(ev) {
    if (picking || performance.now() - picked < 500) return;   // a pick owns its whole gesture
    const target = ev.target instanceof Element ? ev.target : null;
    if (target?.closest(".fpl-annot-ui")) return;
    const sel = getSelection();
    if (ev.altKey) { if (sel.rangeCount && !sel.isCollapsed) piece(sel); return; }   // Alt: a piece, or an Alt-click
    if (!sel.rangeCount || sel.isCollapsed) {
      const m = target?.closest("mark.fact");
      if (!m) { if (editing) { closeEditor(); layout(); } return; }
      const own = all.find((r) => r.id === m.dataset.id), row = wholeOf(own.id) ?? own;   // a piece answers for its whole
      if (mode() !== "kantlijn") {
        open.has(row.id) ? open.delete(row.id) : (open.clear(), open.add(row.id));
        layout();
        hot(row.id);
        return;
      }
      hot(row.id);
      const card = margin.querySelector(`.fpl-card[data-id="${CSS.escape(row.id)}"]`);
      if (row.mine) { edit(row, card, m.getBoundingClientRect()); hot(row.id); }
      else if (card && wide()) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
      return;
    }
    if (mode() !== "kantlijn") return;
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)) return;
    if ([...body.querySelectorAll(".fpl-scrunched")].some((l) => range.intersectsNode(l))) {
      // shown() keeps folded text (the quote finder needs it whole), so the quote would hold what was never seen
      sel.removeAllRanges();
      toast("De selectie loopt door een band: open die eerst");
      return;
    }
    const ix = shown(), [s, e] = bounds(ix, range);
    if (s >= e) return;
    const seed = { text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s),
      suffix: ix.flat.slice(e, e + AROUND) };
    const at = range.getBoundingClientRect();
    sel.removeAllRanges();
    wrap(ix, s, e, { id: "draft", mine: true });   // the span stays lit while its fact is written
    edit(seed, null, at);
    hot("draft");
  }
  let pieces = [];   // the span rows Alt-selected so far, bundled by Enter
  let pieced = 0;    // when the last piece was taken
  let adding = null; // the id of a parts row of ours the next pieces join, armed by "Deel erbij…"
  /** Esc, Enter, the editor's Esc or leaving Kantlijn: the armed parts row takes no more pieces. */
  function disarm() {
    if (!adding) return;
    toast(`Gestopt: ${adding} heeft ${local().find((r) => r.id === adding)?.targets.length ?? 0} delen`);
    adding = null;
  }
  /** "Deel erbij…": the next Alt-selects join this parts row, until Esc or Enter. */
  function arm(id) {
    if (mode() !== "kantlijn") { toast("Delen schrijf je in de stand Kantlijn (a)"); return; }
    if (picking) unpick();
    const loose = pieces.length ? ": de losse delen blijven losse spans" : "";
    pieces = [];
    adding = id;
    toast(`Delen erbij voor ${id}${loose} · Alt-selecteer het volgende · Esc stopt`);
  }
  /** Alt-select: the selection becomes a span row of this browser, the next piece of a discontinuous span. */
  function piece(sel) {
    pieced = performance.now();   // this gesture is a selection, whatever comes of it: its click is no Alt-click
    if (mode() !== "kantlijn") { sel.removeAllRanges(); toast("Delen schrijf je in de stand Kantlijn (a)"); return; }
    const range = sel.getRangeAt(0);
    if (!body.contains(range.commonAncestorContainer)
      || [...body.querySelectorAll(".fpl-scrunched")].some((l) => range.intersectsNode(l))) { sel.removeAllRanges(); return; }
    const ix = shown(), [s, e] = bounds(ix, range);
    sel.removeAllRanges();
    if (s >= e) return;
    const pr = adding && local().find((r) => r.id === adding);
    if (adding && !pr) adding = null;   // the bundle went meanwhile: this starts a new one
    // a fresh row is in no bundle, so the test is by place: text a piece of a whole already covers
    const hit = all.filter((r) => r.labels?.[0] === "parts" && !partsOf(r.id) && (shows(r) || r.id === pr?.id)).filter((p) => leavesOf(p).some((t) => {
      const r = all.find((x) => x.id === t), at = typeof r?.text === "string" && find(ix, r);
      return Array.isArray(at) && at[0] < e && s < at[1];
    }));
    const mine = pr ? (wholeOf(pr.id) ?? pr).id : null;   // the selection touches the bundle being made: refused, whatever else it touches
    if (hit.some((h) => h.id === mine || pieces.includes(h.id))) { toast(`Dat is al een deel van ${pr?.id ?? "deze bundel"}`); return; }
    if (hit.length > 1) { toast(`Dat loopt over ${hit.length} bundels: kies er één`); return; }
    const owner = hit[0];
    if (owner) {   // a piece of a piece: the whole that text is in joins as one piece
      if (pr) {
        save(pr, { targets: [...pr.targets, owner.id] });
        draw();
        toast(`Bundel ${owner.id} is deel ${pr.targets.length + 1} van ${pr.id} · Alt-selecteer het volgende · Esc stopt`);
        return;
      }
      pieces.push(owner.id);
      draw();
      toast(`Deel ${pieces.length}: bundel ${owner.id}${pieces.length > 1 ? " · Enter bundelt" : ""} · Alt-selecteer het volgende · Esc stopt`);
      return;
    }
    save({ text: ix.flat.slice(s, e), prefix: ix.flat.slice(Math.max(0, s - AROUND), s), suffix: ix.flat.slice(e, e + AROUND) },
      { note: "", labels: [] });
    const id = local().at(-1).id;
    if (pr) {
      save(pr, { targets: [...pr.targets, id] });
      draw();
      toast(`Deel ${pr.targets.length + 1} van ${pr.id} · Alt-selecteer het volgende · Esc stopt`);
      return;
    }
    pieces.push(id);
    draw();
    toast(`Deel ${pieces.length}${pieces.length > 1 ? ": Enter bundelt" : ""} · Alt-selecteer het volgende · Esc stopt`);
  }
  /** Enter: the pieces become one span, a parts row, and the editor opens for a fact about it. */
  function bundle() {
    const live = new Set([...local().filter((r) => typeof r.text === "string"), ...all.filter((r) => r.labels?.[0] === "parts" && !partsOf(r.id))].map((r) => r.id));
    const ps = pieces.filter((id) => live.has(id));   // a piece deleted meanwhile is no piece
    pieces = [];
    if (ps.length < 2) { toast("Minder dan twee delen over: niets gebundeld"); draw(); return; }
    save({ targets: ps }, { note: "", labels: ["parts"] });
    const id = local().at(-1).id;
    draw();
    const m = anchorsOf(id)[0];
    edit({ targets: [id] }, null, (m ?? body).getBoundingClientRect());
  }

  /** The address under a click on a number drawn before a block or sentence, or null. */
  function numberAt(ev) {
    const t = ev.target instanceof Element ? ev.target : null;
    const unit = t?.closest(".fpl-s, .fpl-p");
    if (!unit || !document.body.classList.contains("fpl-numbered")) return null;
    const before = getComputedStyle(unit, "::before");
    const w = parseFloat(before.width) || 0;
    if (!w || before.display === "none") return null;
    const r = unit.getClientRects()[0];
    if (!r) return null;
    if (unit.classList.contains("fpl-p")) {   // the number stands in the left gutter
      const gap = parseFloat(before.marginRight) || 0;
      return ev.clientX < r.left - gap && ev.clientX > r.left - gap - w - 4 ? unit.id : null;
    }
    return ev.clientX >= r.left - 2 && ev.clientX <= r.left + w + 2 && ev.clientY >= r.top && ev.clientY <= r.bottom ? unit.id : null;
  }
  /** Alt-click a clause cycles its tfa value; Alt-Shift-click arms a resumes pick from it. */
  document.addEventListener("click", (ev) => {
    if (!ev.altKey || picking || mode() === "lezen" || performance.now() - pieced < 500) return;
    const c = ev.target.closest?.(".fpl-c[id]") ?? ev.target.closest?.(".fpl-s[id]");   // a one-clause sentence has no .fpl-c
    if (!c || !body.contains(c)) return;
    ev.preventDefault();
    ev.stopImmediatePropagation();
    if (!ev.shiftKey) { cycle(c.id); return; }
    adding = null;   // one armed gesture at a time
    picking = { from: c.id, kind: "resumes" };
    document.body.classList.add("fpl-picking");
    toast(`Klik de eerdere bijzin die ${c.id} weer opneemt. Esc breekt af.`);
  }, true);
  document.addEventListener("click", (ev) => {
    const id = numberAt(ev);
    if (!id) return;
    ev.preventDefault();
    getSelection()?.removeAllRanges();
    history.replaceState(null, "", `#${id}`);
    sync();
    const url = location.href;
    navigator.clipboard?.writeText(url).then(() => toast(`Adres gekopieerd: #${id}`), () => toast(`#${id}`));
    if (mode() === "kantlijn") edit({ targets: [id] }, null, document.getElementById(id).getBoundingClientRect());
  });
  document.addEventListener("mouseup", pointerDone);
  document.addEventListener("touchend", (ev) => setTimeout(() => pointerDone(ev), 0));
  body.addEventListener("mouseover", (ev) => { const m = ev.target.closest?.("mark.fact"); if (m && !editing) hot(m.dataset.id); });
  body.addEventListener("mouseout", (ev) => { if (ev.target.closest?.("mark.fact") && !editing) hot(null); });
  body.addEventListener("mouseover", (ev) => {   // an address in a coref row lights its chain too
    const u = !ev.target.closest?.("mark.fact") && ev.target.closest?.(".fpl-c[id], .fpl-s[id], .fpl-p[id]");
    for (const n of body.querySelectorAll(".fpl-coref")) n.classList.remove("fpl-coref");
    if (u) for (const t of corefOf(u.id)) for (const e of [...marksOf(t), document.getElementById(t)])
      if (e && body.contains(e)) e.classList.add("fpl-coref");
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && drag?.live && !drag.cancelled) { ev.preventDefault(); cancelDrag(); return; }
    if (picking && !picking.kind && cardMenu.hidden && !ev.metaKey && !ev.ctrlKey && !ev.altKey
      && !ev.target.closest?.("input, textarea, select, [contenteditable]") && walk(ev)) return;
    if (stretching?.keys && (ev.key === "Escape" || ev.key === "Enter")) {   // a stretch by keys: Enter saves, Esc puts back
      ev.preventDefault();
      const id = stretching.id;
      if (ev.key === "Enter") keepStretch(); else { dropStretch(); toast("Teruggezet"); }
      lines.querySelector(`.fpl-knob[data-id="${CSS.escape(id)}"]`)?.focus({ preventScroll: true });
      return;
    }
    const knobId = document.activeElement?.closest?.(".fpl-knob")?.dataset.id;
    if (knobId && ev.shiftKey && (ev.key === "ArrowRight" || ev.key === "ArrowLeft") && !ev.metaKey && !ev.ctrlKey && !ev.altKey && !drag) {
      ev.preventDefault();
      nudge(knobId, ev.key === "ArrowRight" ? 1 : -1);
      return;
    }
    if (ev.key === "Escape" && !cardMenu.hidden) {   // a card's menu: closed, focus back on its ⋯
      const id = menuOf;
      shut();
      if (id) cardEl(id)?.querySelector(".fpl-card-more")?.focus({ preventScroll: true });
      return;
    }
    if (ev.key === "Escape" && (!menu.hidden || !panel.hidden || !views.hidden)) {   // an open popover first, focus back to its button
      const back = !views.hidden ? viewBtn : menu.hidden ? filterBtn : moreBtn, inside = [menu, panel, views].some((x) => x.contains(document.activeElement));
      shut();
      if (inside) back.focus();
      return;
    }
    const g = document.querySelector(".fpl-graph");   // an open graph takes Esc first, wherever focus is
    if (ev.key === "Escape" && g) { if (!g.letGo()) g.close(); return; }   // a choice of cards first, then the plane
    if (ev.key === "Escape" && editing) { closeEditor(); layout(); disarm(); return; }
    if (ev.key === "Escape" && picking) { unpick(); toast("Afgebroken"); return; }
    if (ev.key === "Escape" && openId && !ev.target.closest?.("input, textarea, [contenteditable]")) { openId = null; layout(); return; }
    if (adding && (ev.key === "Escape" || ev.key === "Enter") && !ev.defaultPrevented
      && !ev.target.closest?.(ev.key === "Enter" ? "input, textarea, select, [contenteditable], button, a, [role=button], .fpl-chip, summary"
        : "input, textarea, select, [contenteditable]")) {
      ev.preventDefault();
      disarm();
      return;
    }
    if (pieces.length && (ev.key === "Escape" || ev.key === "Enter") && !ev.defaultPrevented
      && !ev.target.closest?.("input, textarea, select, [contenteditable], button, a, [role=button], .fpl-chip, summary")) {
      ev.preventDefault();
      if (ev.key === "Enter" && pieces.length > 1) bundle();
      else { toast(pieces.length > 1 ? "Gestopt: de delen blijven losse spans" : "Gestopt"); pieces = []; }
      return;
    }
    if (ev.key === "Escape" && bands.length && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      setBands(bands.slice(0, -1));
      return;
    }
    const typing = ev.defaultPrevented || ev.target.closest?.("input, textarea, select, [contenteditable], .fpl-editor");
    // back to where the page stood before a jump from the graph: our own stack, since browser Back is Cmd+[ on a Mac
    // a step of the graph goes back as Back does, and its jump with it
    const stepped = plane?.view === "graph"
      && history.state?.fplGraph !== undefined;
    const altLeft = ev.key === "ArrowLeft" && ev.altKey && !ev.metaKey
      && !ev.ctrlKey && !ev.shiftKey && !typing;
    if (altLeft && (jumps.length || stepped)) {
      ev.preventDefault();
      const j = jumps.pop();
      if (j) scrollTo({ top: j.y, behavior: "smooth" });
      if (stepped && (!j || j.step)) history.back();
      return;
    }
    if (ev.key === "Escape" && reading && !typing) { read(null); return; }
    if (ev.key === "?" && !typing && !ev.metaKey && !ev.ctrlKey && !ev.altKey) { ev.preventDefault(); menu.hidden || !menu.classList.contains("fpl-keysheet") ? keysheet() : shut(); return; }
    const plainish = !typing && !ev.metaKey && !ev.ctrlKey && !ev.altKey;
    // / is the margin's search in Kantlijn; elsewhere it stays Quarto's, with f and s (feedback 22)
    if (ev.key === "/" && plainish && mode() === "kantlijn") { ev.preventDefault(); seek(); return; }
    const digit = /^Digit([1-4])$/.exec(ev.code);   // by code: Shift+1 is "!" on the key
    if (digit && plainish && mode() !== "lezen" && cardMenu.hidden) { ev.preventDefault(); toggleLayer(FOUR[digit[1] - 1], ev.shiftKey); return; }
    if (typing || ev.metaKey || ev.ctrlKey || ev.altKey || ev.shiftKey) return;
    if (ev.key === "l") {   // Verbind met…: the knob or card holding the focus, else the card under the mouse
      ev.preventDefault();
      if (mode() !== "kantlijn") { toast("Verbinden doe je in de stand Kantlijn (a)"); return; }
      const c = margin.querySelector(".fpl-card:focus-within[data-id], .fpl-card.is-hot[data-id]");
      const id = document.activeElement?.closest?.(".fpl-knob")?.dataset.id ?? c?.dataset.id;
      if (!id || id === "draft") { toast("l verbindt de kaart onder de muis: wijs er eerst een aan"); return; }
      pick(id);
      return;
    }
    if (ev.key === "j" || ev.key === "k") { ev.preventDefault(); step(ev.key === "j" ? 1 : -1); return; }
    if (ev.key === "b") { ev.preventDefault(); boom(); return; }
    if (ev.key === "Enter" && reading && !ev.target.closest?.("button, a, [role=button]")) {
      ev.preventDefault();
      if (mode() === "kantlijn") edit({ targets: [reading.id] }, null, reading.getBoundingClientRect());
      else toast("Een feit schrijf je in de stand Kantlijn (a)");
      return;
    }
    if (ev.key === "a" && !ev.metaKey && !ev.ctrlKey && !ev.altKey
      && !ev.target.closest?.("input, textarea, [contenteditable]")) {
      const m = MODES[(MODES.indexOf(mode()) + 1) % MODES.length];
      if (m !== "kantlijn") disarm();
      mode(m);
      draw();
    }
  });

  let timer = 0;
  // not while editing: a phone's keyboard resizes the window, and the draft would go
  const relayout = () => { clearTimeout(timer); timer = setTimeout(() => { if (!editing) layout(); }, 120); };
  addEventListener("resize", relayout);
  document.fonts?.ready.then(relayout);

  document.body.append(pop, menu, views, panel, cardMenu);
  const decisions = (snap ? Promise.resolve(snap.decisions ?? "") : fetch(`${stem}.decisions.tsv`).then((r) => (r.ok ? r.text() : "")))
    .catch(() => "");
  Promise.all([(snap ? Promise.resolve(snap.rows) : fetch(`${stem}.facts.json`).then((r) => (r.ok ? r.json() : []))).catch(() => []), decisions])
    .then(([got, tsv]) => { ledger = readLedger(tsv); sidecar = Array.isArray(got) ? got : []; draw(); persist();
      sync(); });
})();
