/**
 * SMIPL brand marks.
 *
 * The company logo (navy + red "valve & fitting" wordmark, supplied by SMIPL) is a
 * raster asset in `public/smipl-logo.png`. It is trimmed tight and drawn on a white
 * plate wherever it sits on a dark surface, because the artwork has an opaque white
 * background rather than transparency.
 */

const LOGO_SRC = "/smipl-logo.png";

/** Intrinsic aspect ratio of the trimmed asset (173 x 116). */
const LOGO_RATIO = 173 / 116;

function logoHeight(size) {
  // `size` is a square-ish budget from the old SVG mark; the wordmark is wider than
  // it is tall, so derive a readable height and never let it collapse.
  return Math.max(18, Math.round(size * 0.66));
}

export function LogoMark({ size = 38, className = "", alt = "" }) {
  return (
    <img
      src={LOGO_SRC}
      alt={alt}
      width={Math.round(logoHeight(size) * LOGO_RATIO)}
      height={logoHeight(size)}
      className={`brand-logo ${className}`.trim()}
      style={{ height: logoHeight(size) }}
    />
  );
}

export function LogoLockup({ sub = "SMIPL Shipment Desk", large = false }) {
  return (
    <>
      <span className="brand-mark">
        <LogoMark size={large ? 50 : 40} alt="Shreemaruti Instruments Pvt. Ltd." />
      </span>
      <div>
        <div className="brand-name">ShipTrack</div>
        <div className="brand-sub">{sub}</div>
      </div>
    </>
  );
}
