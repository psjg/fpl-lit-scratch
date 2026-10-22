-- Prototype weave: Entangled chunks (```python + "#| id:" / "#| file:") become
-- CWEB-style sections: a numbered label before the code, the "#|" header
-- stripped, and a footer with "See also" and "Used in" links.

local chunks = {}   -- in document order: {name=, first=bool, n=}
local first_of = {} -- name -> section number of its first definition
local all_of = {}   -- name -> list of section numbers
local used_in = {}  -- name -> list of section numbers that reference it

local function header(text)
  local name, kind
  local body = {}
  local in_header = true
  for line in (text .. "\n"):gmatch("(.-)\n") do
    local k, v = line:match("^#|%s*(%w+):%s*(%S+)")
    if in_header and k then
      if k == "id" or k == "file" then name, kind = v, k end
    else
      in_header = false
      table.insert(body, line)
    end
  end
  return name, kind, table.concat(body, "\n")
end

local function anchor(n) return "s" .. n end

local function links(list, skip)
  local out = {}
  for _, n in ipairs(list) do
    if n ~= skip then
      table.insert(out, "[§" .. n .. "](#" .. anchor(n) .. ")")
    end
  end
  return table.concat(out, ", ")
end

function Pandoc(doc)
  local n = 0
  -- first walk: number the chunks and record definitions and uses
  for _, b in ipairs(doc.blocks) do
    if b.t == "CodeBlock" and b.classes:includes("python") then
      local name, kind, body = header(b.text)
      if name then
        n = n + 1
        all_of[name] = all_of[name] or {}
        table.insert(all_of[name], n)
        first_of[name] = first_of[name] or n
        for ref in body:gmatch("<<([%w:/_.%-]+)>>") do
          used_in[ref] = used_in[ref] or {}
          table.insert(used_in[ref], n)
        end
        chunks[b] = { name = name, kind = kind, n = n, body = body }
      end
    end
  end
  -- second walk: label, strip, footer
  local out = {}
  for _, b in ipairs(doc.blocks) do
    local c = chunks[b]
    if c then
      local sign = (first_of[c.name] == c.n) and " ≡" or " +≡"
      local label = c.kind == "file" and ("file " .. c.name) or c.name
      table.insert(out, pandoc.Div(
        pandoc.Para({ pandoc.Strong(pandoc.Str("§" .. c.n)), pandoc.Space(),
          pandoc.Str("⟨" .. label .. " " .. first_of[c.name] .. "⟩" .. sign) }),
        pandoc.Attr(anchor(c.n), { "chunk-label" })))
      table.insert(out, pandoc.CodeBlock(c.body, pandoc.Attr("", { "python" })))
      local foot = {}
      local also = links(all_of[c.name], c.n)
      if also ~= "" then table.insert(foot, "See also " .. also .. ".") end
      local used = links(used_in[c.name] or {}, nil)
      if used ~= "" then table.insert(foot, "Used in " .. used .. ".") end
      if c.kind == "file" then table.insert(foot, "Root of the tangle.") end
      -- CWEB prints a reference with its section number; a code block holds
      -- no links, so the footer resolves each <<ref>> of this chunk instead.
      local refs = {}
      for ref in c.body:gmatch("<<([%w:/_.%-]+)>>") do
        local at = first_of[ref]
        table.insert(refs, "⟨" .. ref .. "⟩ " ..
          (at and ("[§" .. at .. "](#" .. anchor(at) .. ")") or "**undefined**"))
      end
      if #refs > 0 then table.insert(foot, "Refers to " .. table.concat(refs, ", ") .. ".") end
      if #foot > 0 then
        local md = pandoc.read(table.concat(foot, " "), "markdown").blocks
        table.insert(out, pandoc.Div(md, pandoc.Attr("", { "chunk-foot" })))
      end
    else
      table.insert(out, b)
    end
  end
  doc.blocks = out
  return doc
end
