/** A label's lookup key: case, surrounding punctuation and spacing folded. */
export const labelKey = (label: string): string =>
  label
    .normalize("NFC")
    .toLowerCase()
    .replace(/[\s ]+/g, " ")
    .replace(/^[\s(*"'«»–-]+|[\s)!.:,*"'«»–-]+$/g, "");
