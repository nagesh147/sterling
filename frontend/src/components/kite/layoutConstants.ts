/**
 * Geometry shared between the workspace chrome and anything that positions
 * itself against it.
 *
 * The replay dock's floating mode sits directly above the footer. When both
 * sides typed `36` independently, a change to one silently desynced the other.
 */
export const FOOTER_HEIGHT = 36;
