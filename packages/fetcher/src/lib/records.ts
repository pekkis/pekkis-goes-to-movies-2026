/**
 * `record[key]`, but only for the record's own keys. Lookup tables keyed by text from
 * outside (labels, language names, codes) must not find inherited properties: a label
 * "constructor" would otherwise match `Object.prototype.constructor`.
 */
export const own = <V>(
  record: Readonly<Record<string, V>> | undefined,
  key: string,
): V | undefined => (record && Object.hasOwn(record, key) ? record[key] : undefined);
