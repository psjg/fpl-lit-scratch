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
    end
  end
  return doc
end

-- Every heading is numbered below the page's own address: on 01.02.01 Lex
-- the second h2 is 1.2.1.2, its first h3 1.2.1.2.1, so the sidebar and
-- the page count all the way down. The number is a span of Quarto's own
-- class, so the theme sets it like a section number.
function number(doc, addr)
  local base = addr:gsub("%f[%d]0+(%d)", "%1")
  local count = {}
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
    end
  end
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
