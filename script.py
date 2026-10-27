from pathlib import Path
import re
import shutil

path = Path(
    r"c:\Users\lukas\Documents\Paradox Interactive\Hearts of Iron IV"
    r"\mod\NovumVexillum\common\decisions\resource_prospecting_africa.txt"
)
text = path.read_text(encoding="utf-8-sig")
shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))


def block_end(source, opening):
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos + 1
    raise ValueError("Unclosed block")


def find_block(source, key, start=0):
    match = re.search(r"\b" + re.escape(key) + r"\s*=\s*\{", source[start:])
    if not match:
        return None
    begin = start + match.start()
    opening = start + match.end() - 1
    return begin, opening, block_end(source, opening)


def convert(decision):
    if re.search(r"\bstate_target\s*=\s*yes\b", decision):
        return decision

    visible = find_block(decision, "visible")
    allowed = find_block(decision, "allowed")
    if not visible or not allowed:
        return decision

    _, visible_open, visible_end = visible
    visible_body = decision[visible_open + 1 : visible_end - 1]
    state_matches = list(
        re.finditer(r"(?m)^\s*(\d+)\s*=\s*\{", visible_body)
    )

    states = []
    for index, match in enumerate(state_matches):
        end = (
            state_matches[index + 1].start()
            if index + 1 < len(state_matches)
            else len(visible_body)
        )
        state_body = visible_body[match.end() : end]
        flag = re.search(r"\bhas_state_flag\s*=\s*(\w+)", state_body)
        if flag:
            states.append((match.group(1), flag.group(1)))

    if not states:
        return decision

    target_ids = {state_id for state_id, _ in states}

    # Remove the old visibility and highlight blocks.
    for key in ("visible", "highlight_states"):
        found = find_block(decision, key)
        if found:
            begin, _, end = found
            decision = decision[:begin] + decision[end:]

    # Move target-state ownership checks out of available.
    available = find_block(decision, "available")
    if available:
        begin, opening, end = available
        body = decision[opening + 1 : end - 1]
        body = re.sub(
            r"(?m)^\s*controls_state\s*=\s*(\d+)\s*\n",
            lambda m: "" if m.group(1) in target_ids else m.group(0),
            body,
        )
        decision = decision[: opening + 1] + body + decision[end - 1 :]

    target_block = (
        "\n\t\tstate_target = yes\n"
        "\t\ttargets = { " + " ".join(state_id for state_id, _ in states) + " }\n"
        "\t\ttarget_trigger = {\n"
    )
    for state_id, flag in states:
        target_block += (
            "\t\t\tFROM = {\n"
            "\t\t\t\tis_controlled_by = ROOT\n"
            "\t\t\t}\n"
            "\t\t\tFROM = {\n"
            "\t\t\t\tNOT = { has_state_flag = " + flag + " }\n"
            "\t\t\t}\n"
        )
    target_block += "\t\t}\n"

    allowed = find_block(decision, "allowed")
    insert_at = allowed[2]
    return decision[:insert_at] + target_block + decision[insert_at:]


# Find decision blocks by their icon field, then replace from the end
# so earlier character offsets remain valid.
matches = list(re.finditer(r"(?m)^[ \t]+[\w]+\s*=\s*\{", text))
replacements = []
for match in matches:
    opening = text.find("{", match.start(), match.end())
    end = block_end(text, opening)
    decision = text[match.start() : end]
    if re.search(r"\bicon\s*=", decision):
        converted = convert(decision)
        if converted != decision:
            replacements.append((match.start(), end, converted))

for start, end, converted in reversed(replacements):
    text = text[:start] + converted + text[end:]

path.write_text(text, encoding="utf-8-sig", newline="")
print(f"Converted {len(replacements)} decisions. Backup: {path}.bak")