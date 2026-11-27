/* A dispatch UUID as `d` and its first eight hex digits (`d8e030c3f`), in any text; an id of another
   form is kept. The TUI words it the same way (`brand.short_dispatch`). */
const DISPATCH_UUID = /\bdispatch-([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/g;

export const shortDispatch = (text: string): string => text.replace(DISPATCH_UUID, (_whole, head: string) => `d${head}`);
