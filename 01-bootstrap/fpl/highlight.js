/**
 * Syntax colours for the pad without an editor library: a reader of the
 * Monarch tokenizer the playground feeds to Monaco (fpl-language.js, which
 * ide/gen_highlight.py derives from the grammar), and a painter that puts
 * its tokens in a <pre> as coloured spans.
 *
 * The reader covers what that definition uses of Monarch: rules as
 * [regex, action] tried in order at the current position; an action that is
 * a token name, "@brackets", {token, next} with next "@push", "@pop" or a
 * state to push, or {cases} whose "~regex" guards match the whole token and
 * whose "@default" ends the search. The state stack carries over line ends,
 * as Monarch's does. Anything the definition does not use is not read.
 */

/** A token's colour and style, by the longest matching dotted prefix. */
function styled(palette, token) {
	for (let name = token; name; name = name.slice(0, name.lastIndexOf("."))) {
		if (name in palette) return palette[name];
	}
	return null;
}

/** The rules of each state, their regexes anchored at the position. */
function compiled(definition) {
	const states = {};
	for (const [name, rules] of Object.entries(definition.tokenizer)) {
		states[name] = rules.map(([regex, action]) => [new RegExp("^(?:" + regex + ")"), action]);
	}
	return states;
}

/** The token an action gives for the text `hit`, moving the state stack. */
function resolved(action, hit, stack) {
	if (typeof action === "string") {
		return action === "@brackets" ? "delimiter.bracket" : action;
	}
	if (action.cases) {
		for (const [guard, then] of Object.entries(action.cases)) {
			const taken = guard === "@default"
				|| (guard.startsWith("~") && new RegExp("^(?:" + guard.slice(1) + ")$").test(hit));
			if (taken) return resolved(then, hit, stack);
		}
		return "";
	}
	if (action.next === "@push") stack.push(stack[stack.length - 1]);
	else if (action.next === "@pop") stack.pop();
	else if (action.next) stack.push(action.next.replace(/^@/, ""));
	return action.token;
}

/**
 * Tokenize `text` with the Monarch `definition`.
 * @returns {[string, string][][]} per line, [text, token] pairs that join back to the line
 */
export function tokenized(definition, text) {
	const states = compiled(definition);
	const stack = ["root"];
	return text.split("\n").map(line => {
		const tokens = [];
		for (let at = 0; at < line.length;) {
			const rest = line.slice(at);
			const rules = states[stack[stack.length - 1]] ?? states.root;
			const found = rules.map(([regex, action]) => [regex.exec(rest)?.[0], action]).find(([hit]) => hit);
			if (!found) {
				tokens.push([rest[0], definition.defaultToken ?? ""]);
				at += 1;
				continue;
			}
			const [hit, action] = found;
			tokens.push([hit, resolved(action, hit, stack)]);
			at += hit.length;
		}
		return tokens;
	});
}

/**
 * Paint `text` into `pre` as coloured spans, one line per text line.
 * @param {Record<string, {color: string, style?: string, weight?: string}>} palette by token prefix
 */
export function painted(pre, definition, text, palette) {
	const lines = tokenized(definition, text);
	pre.replaceChildren(...lines.flatMap((tokens, i) => {
		const spans = tokens.map(([hit, token]) => {
			const span = document.createElement("span");
			span.textContent = hit;
			const look = styled(palette, token);
			if (look) {
				span.style.color = look.color;
				if (look.style) span.style.fontStyle = look.style;
				if (look.weight) span.style.fontWeight = look.weight;
			}
			return span;
		});
		return i < lines.length - 1 ? [...spans, "\n"] : spans;
	}), "\n");
}
