/**
 * Outside links (ticket pages, cinemas' websites) come from the cinemas' own pages. The model
 * already accepts only http(s), but the API is a boundary too: a link with any other scheme
 * (`javascript:`, `data:`) is never printed as an `href`, whatever the data says.
 */
export const safeHref = (url: string | null | undefined): string | undefined => {
  if (!url) {
    return undefined;
  }
  try {
    const { protocol } = new URL(url);
    return protocol === "https:" || protocol === "http:" ? url : undefined;
  } catch {
    return undefined;
  }
};
