-- The sidebar title is the address in the filename plus the note's own
-- name. A first heading that only repeats that name is dropped. The
-- Marimo setup cell is the notebook's, not the essay's. A link that
-- names a sibling note opens that chapter.

local function address(path)
  local stem = path:match("([^/]+)%.[^%.]+$") or ""
  local addr, slug = stem:match("^(%d%d%.%d%d%.%d%d%.%d%d)%-(.+)$")
  if addr then
    return addr, slug
  end
  addr, slug = stem:match("^(%d%d%.%d%d%.%d%d)%-(.+)$")
  if addr then
    return addr, slug
  end
  return stem:match("^(%d%d%.%d%d)%-(.+)$")
end

local function nice(slug)
  return (slug:gsub("-", " "):gsub("(%a)([%w']*)", function(a, rest)
    return a:upper() .. rest
  end))
end

-- The commit a page was rendered from, for the annotation overlay
-- (assets/fpl-annot.js) to write on the rows it exports. It is read at
-- render time, so a published page names the commit publish.sh ran
-- on, not the one that last stamped the site config. A dirty tree is
-- still that commit: render from a clean one to publish.
local commit = nil

local function stamp()
  if commit == nil then
    commit = pandoc.pipe("git", { "rev-parse", "HEAD" }, ""):gsub("%s+$", "")
  end
  quarto.doc.include_text(
    "in-header",
    '<meta name="fpl-commit" content="' .. commit .. '">'
  )
end

function Pandoc(doc)
  if quarto.doc.is_format("html") then
    stamp()
  end
  local file = ""
  if quarto.doc ~= nil and quarto.doc.input_file ~= nil then
    file = quarto.doc.input_file
  else
    file = PANDOC_STATE.input_file or ""
  end
  local addr, slug = address(file)
  local bare = pandoc.utils.stringify(doc.meta.title or "")
  if addr then
    if bare == "" and slug then
      bare = nice(slug)
    end
    if bare:sub(1, #addr) ~= addr then
      bare = addr .. " " .. bare
      doc.meta.title = pandoc.MetaInlines({ pandoc.Str(bare) })
    end
  end
  local blocks = {}
  local dropped = false
  for _, block in ipairs(doc.blocks) do
    if not dropped and block.t == "Header" and block.level == 1 then
      local text = pandoc.utils.stringify(block.content)
      if text == bare or (addr and text == (addr .. " " .. bare)) then
        dropped = true
      else
        table.insert(blocks, block)
      end
    elseif block.t == "CodeBlock" and block.attributes["name"] == "setup" then
      -- the notebook preamble, not part of the reading
    else
      table.insert(blocks, block)
    end
  end
  doc.blocks = blocks
  if FORMAT:match("html") then
    doc = nest(doc)
    if addr then
      number(doc, addr)
      files(doc)
    end
  end
  return doc
end

-- Every heading is numbered below the page's own address: on 01.02.01 Lex
-- the second h2 is 1.2.1.2, its first h3 1.2.1.2.1, so the sidebar and
-- the page count all the way down. The number is a span of Quarto's own
-- class, so the theme sets it like a section number.
--
-- Below the headings the blocks count too, paragraphs and code alike,
-- and a paragraph's sentences and clauses: the fourth block under 1.2.1.3
-- is §4 (§4:C when it is code), its second sentence §4.2, that
-- sentence's third clause §4.2.3, the twelfth line of code block 5
-- §5:12. A block is a div (class fpl-p, data-n, data-kind P or C, id
-- <heading>/b4), a sentence a span (fpl-s, id <heading>/b4s2), a clause
-- a span (fpl-c, id ...s2c3); a code line gets its id (...b5l12) from
-- fpl-nav.js, since Quarto draws the lines after this filter. The
-- blocks before the first heading count under the page itself, with
-- ids without a heading (b2). The overlay shows the numbers outside
-- the reading stand, the clauses' only while the sentence is hovered.
-- A sentence ends at a word ending in . ? or ! (closing quotes or
-- brackets after it) that is not a one-letter or known abbreviation.
local ABBR = { ["e.g."] = true, ["i.e."] = true, ["vs."] = true, ["cf."] = true,
  ["etc."] = true, ["Mr."] = true, ["Dr."] = true, ["St."] = true, ["No."] = true }

local function ends_sentence(word)
  local core = word:gsub("[%)%]'\"\u{2019}\u{201D}]+$", "")
  if not core:match("[%.%?!]$") then
    return false
  end
  if ABBR[core] or core:match("^%a%.$") or core:match("^%d+%.$") then
    return false
  end
  return true
end

-- Inlines cut into spans at the words `stop` says, numbered from 1 with
-- the class and id suffix given; the space after a cut stays outside.
local function cut(inlines, id, suffix, class, stop)
  local out, cur, n = pandoc.Inlines({}), pandoc.Inlines({}), 0
  local function flush()
    if #cur == 0 then
      return
    end
    n = n + 1
    out:insert(pandoc.Span(cur, pandoc.Attr(id .. suffix .. n, { class }, { ["data-n"] = tostring(n) })))
    cur = pandoc.Inlines({})
  end
  local skip = false
  for i, x in ipairs(inlines) do
    if skip then
      skip = false
    else
      cur:insert(x)
      local nxt = inlines[i + 1]
      if x.t == "Str" and nxt and (nxt.t == "Space" or nxt.t == "SoftBreak") and stop(x.text) then
        flush()
        out:insert(nxt)
        skip = true
      end
    end
  end
  flush()
  return out, n
end

-- A clause, for the address only (shown while the sentence is hovered),
-- ends at a word ending in , ; : or a dash: the segments a reader points
-- at, not what a parser would call a clause.
local function ends_clause(word)
  return word:match("[,;:\u{2014}\u{2013}]$") ~= nil or word == "-" or word == "--"
end

local function sentences(inlines, id)
  local out, n = cut(inlines, id, "s", "fpl-s", ends_sentence)
  for _, span in ipairs(out) do
    if span.t == "Span" then
      local parts, m = cut(span.content, span.identifier, "c", "fpl-c", ends_clause)
      if m > 1 then
        span.content = parts
      end
    end
  end
  return out, n
end

function number(doc, addr)
  local base = addr:gsub("%f[%d]0+(%d)", "%1")
  local count, head, para = {}, "", 0
  local blocks = pandoc.List({})
  local section = base
  local function id_of(n)
    return (head ~= "" and head .. "/" or "") .. "b" .. n
  end
  for _, block in ipairs(doc.blocks) do
    if block.t == "Header" and block.level >= 2 then
      for level = block.level + 1, #count do
        count[level] = nil
      end
      count[block.level] = (count[block.level] or 0) + 1
      local parts = { base }
      for level = 2, block.level do
        table.insert(parts, tostring(count[level] or 1))
      end
      local num = pandoc.Span(
        { pandoc.Str(table.concat(parts, ".")) },
        pandoc.Attr("", { "header-section-number" })
      )
      block.content:insert(1, pandoc.Space())
      block.content:insert(1, num)
      head, para, section = block.identifier, 0, table.concat(parts, ".")
      blocks:insert(block)
    elseif block.t == "Para" then
      para = para + 1
      local id = id_of(para)
      local inl, n = sentences(block.content, id)
      blocks:insert(pandoc.Div({ pandoc.Para(inl) },
        pandoc.Attr(id, { "fpl-p" }, { ["data-n"] = tostring(para), ["data-kind"] = "P", ["data-s"] = tostring(n), ["data-addr"] = section })))
    elseif block.t == "CodeBlock" then
      para = para + 1
      local _, lines = block.text:gsub("\n", "")
      blocks:insert(pandoc.Div({ block },
        pandoc.Attr(id_of(para), { "fpl-p" }, { ["data-n"] = tostring(para), ["data-kind"] = "C", ["data-l"] = tostring(lines + 1), ["data-addr"] = section })))
    else
      blocks:insert(block)
    end
  end
  doc.blocks = blocks
end

-- A heading's anchor is its path: an h3 under "Strings and comments"
-- is #strings-and-comments/counted, so the URL reads
-- page#scope/subscope and the sidebar (fpl-nav.js) nests the same way.
-- Links on the page to the old anchors are rewritten with them; links
-- from other pages are not.
function nest(doc)
  local path, renamed = {}, {}
  for _, block in ipairs(doc.blocks) do
    if block.t == "Header" and block.identifier ~= "" then
      for level = block.level, #path do
        path[level] = nil
      end
      local own = block.identifier
      local parent = path[block.level - 1]
      if parent then
        local id = parent .. "/" .. own
        renamed[own] = id
        block.identifier = id
      end
      path[block.level] = block.identifier
    end
  end
  if next(renamed) == nil then
    return doc
  end
  return doc:walk({
    Link = function(link)
      local old = link.target:match("^#(.+)$")
      if old and renamed[old] then
        link.target = "#" .. renamed[old]
      end
      return link
    end,
  })
end

function Link(link)
  if FORMAT == "html" then
    link.target = link.target:gsub("%.md$", ".html")
  end
  return link
end

-- The files a page tangles, as an outline at its end: per file its
-- chunks in file order, each a link to the chunk's page address. The
-- header form is lit's (.harness/tools/lit/lit/web.py): the name line
-- opens with the chunk's place, a dotted number (3.1 is under 3), and
-- the lines after it name a file each, a place of their own first when
-- the chunk sits elsewhere in that file. A chunk another chunk uses is shown
-- under it, by its place. A page without such headers shows nothing.
local function place_key(place)
  local key = {}
  for n in place:gmatch("%d+") do
    table.insert(key, tonumber(n))
  end
  return key
end

local function before(a, b)
  local ka, kb = place_key(a), place_key(b)
  for i = 1, math.max(#ka, #kb) do
    if ka[i] == nil then return true end
    if kb[i] == nil then return false end
    if ka[i] ~= kb[i] then return ka[i] < kb[i] end
  end
  return false
end

local function chunk_of(block)
  local code = block.content[1]
  local header = code.text:match("^<<(.-)>>%+?=")
  if not header or code.text:match("^<<.->>%+=") then
    return nil
  end
  local lines = {}
  for line in (header .. "\n"):gmatch("([^\n]*)\n") do
    table.insert(lines, line)
  end
  local place, name = lines[1]:match("^(%d[%d%.]*)%s+(.+)$")
  if not place then
    name, place = lines[1], nil
  end
  local files = {}
  for i = 2, #lines do
    local own, path = lines[i]:match("^%s*(%d[%d%.]*)%s+(%S+)%s*$")
    if not path then
      path = lines[i]:match("^%s*(%S+)%s*$")
    end
    if path then
      table.insert(files, { path = path, place = own or place })
    end
  end
  return { name = (name:gsub("%s+", " ")), place = place, files = files,
    id = block.identifier, n = block.attributes["data-n"], addr = block.attributes["data-addr"] }
end

function files(doc)
  local out, paths = {}, {}
  for _, block in ipairs(doc.blocks) do
    if block.t == "Div" and block.attributes["data-kind"] == "C" then
      local c = chunk_of(block)
      if c then
        for _, f in ipairs(c.files) do
          if f.place then
            if not out[f.path] then
              out[f.path] = {}
              table.insert(paths, f.path)
            end
            table.insert(out[f.path], { place = f.place, chunk = c })
          end
        end
      end
    end
  end
  if #paths == 0 then
    return
  end
  table.sort(paths)
  local blocks = { pandoc.Header(2, { pandoc.Str("Files") }, pandoc.Attr("files", { "fpl-files" })) }
  for _, path in ipairs(paths) do
    table.sort(out[path], function(x, y) return before(x.place, y.place) end)
    table.insert(blocks, pandoc.Para({ pandoc.Code(path) }))
    for _, item in ipairs(out[path]) do
      local c = item.chunk
      local _, depth = item.place:gsub("%.", "")
      table.insert(blocks, pandoc.Div({ pandoc.Plain({
        pandoc.Span({ pandoc.Str(item.place) }, pandoc.Attr("", { "fpl-place" })), pandoc.Space(),
        pandoc.Link({ pandoc.Str((c.addr or "") .. " §" .. (c.n or "?") .. ":C") }, "#" .. c.id, "", pandoc.Attr("", { "fpl-addr" })),
        pandoc.Space(), pandoc.Str(c.name) }) },
        pandoc.Attr("", { "fpl-part" }, { ["data-depth"] = tostring(depth) })))
    end
  end
  doc.blocks:insert(pandoc.Div(blocks, pandoc.Attr("", { "fpl-files" })))
end
