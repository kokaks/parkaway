<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover, interactive-widget=resizes-content"><meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
<meta name="theme-color" content="#14151a" />
<meta name="apple-mobile-web-app-title" content="parkaway" />
<meta name="application-name" content="parkaway" />
<title>parkaway</title>

<!-- parkaway icon: ONE vector logo served by the backend (/icon.svg and /icon-maskable.svg).
     The browser tab and the PWA manifest use the SVG directly. iOS only accepts a PNG
     apple-touch-icon, so this script rasterises the very same vector in the browser -
     no image file is stored anywhere. -->
<link rel="icon" type="image/svg+xml" href="/icon.svg" />
<link rel="manifest" href="/manifest.json" />
<link rel="apple-touch-icon" id="apple-touch-icon" href="/icon-maskable.svg" />
<script>
(function () {
  try {
    var img = new Image();
    img.onload = function () {
      var c = document.createElement('canvas');
      c.width = c.height = 180;
      c.getContext('2d').drawImage(img, 0, 0, 180, 180);
      document.getElementById('apple-touch-icon').href = c.toDataURL('image/png');
    };
    img.src = '/icon-maskable.svg';
  } catch (e) { /* the SVG link above stays as a fallback */ }
})();
</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css" />
<link rel="stylesheet" href="https://unpkg.com/@geoman-io/leaflet-geoman-free@2.20.4/dist/leaflet-geoman.css" integrity="sha384-++juJE6hRzkkV4Ri9H2C+3yjCTdEk4PaZxptm3cpgKKjuMcAHErn35Q/0sGitZCR" crossorigin="anonymous" />

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://unpkg.com/@geoman-io/leaflet-geoman-free@2.20.4/dist/leaflet-geoman.js" integrity="sha384-/394di3hXbPgMeiEK2waLpRTbD59HEJM2xBFqT/w5K2S+xdv4txKr7W/YG6x7Fbs" crossorigin="anonymous"></script>

{% if ga4_id %}
<!-- Google Analytics 4. Only injected when GA4_MEASUREMENT_ID is set on the
     server, so local/dev instances never send analytics traffic. -->
<script async src="https://www.googletagmanager.com/gtag/js?id={{ ga4_id }}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){ dataLayer.push(arguments); }
  gtag('js', new Date());
  // send_page_view stays on (default) for automatic visit/session counting;
  // anonymize_ip is on as a privacy-conscious default.
  gtag('config', '{{ ga4_id }}', { anonymize_ip: true });
  window.GA4_ENABLED = true;
</script>
{% else %}
<script>window.GA4_ENABLED = false;</script>
{% endif %}

<style>
  :root {
    --basalt-950: #14151a;
    --basalt-900: #1b1d24;
    --basalt-800: #24262f;
    --basalt-700: #32343f;
    --basalt-line: #3a3d4a;
    --fog: #9498a6;
    --paper: #eef0f4;
    --apricot: #f5a536;
    --apricot-dim: #7a5a2a;
    --tuff-pink: #d9808a;
    --leaf: #34c77b;
    --alert: #e2574c;
    --sapphire: #4d8ff0;
    --unavailable: #f39c12;

    /* Text is white; icons keep the apricot accent. */
    --ui-text: var(--paper);
    --ui-icon: var(--apricot);
    --float-bg: rgba(20, 21, 26, 0.94);
    --sheet-radius: 28px;
    --ease: cubic-bezier(0.2, 0.8, 0.2, 1);
    --ease-open: cubic-bezier(.22, .9, .3, 1);
    --ease-close: cubic-bezier(.45, .05, .3, 1);
    --peek: 92px;                       /* how much of a collapsed sheet stays on screen (handle + one row) */

    /* Device Safe Area insets to avoid notches, islands, and rounded corners */
    --safe-top: env(safe-area-inset-top, 0px);
    --safe-bottom: env(safe-area-inset-bottom, 0px);
    --safe-left: env(safe-area-inset-left, 0px);
    --safe-right: env(safe-area-inset-right, 0px);

    /* Single-colour line icons (CSS masks, so they take currentColor) */
    --i-layers: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3.5' y='3.5' width='12' height='12' rx='3.5'/%3E%3Cpath d='M8.5 20.5h8a4 4 0 0 0 4-4v-8'/%3E%3C/svg%3E");
    --i-arrow: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 12h14M13 6l6 6-6 6'/%3E%3C/svg%3E");
    --i-clock: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='8.5'/%3E%3Cpath d='M12 7.500V12l3 2'/%3E%3C/svg%3E");
    --i-locate: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3.5 19.5 20 12 16 4.5 20z'/%3E%3C/svg%3E");
    --i-search: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='11' cy='11' r='6.500'/%3E%3Cpath d='m16 16 4.500 4.500'/%3E%3C/svg%3E");
    --i-map: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M9 4 3.500 6v14L9 18l6 2 5.500-2V4L15 6z'/%3E%3Cpath d='M9 4v14M15 6v14'/%3E%3C/svg%3E");
    --i-food: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 3v8M4.500 3v4.500a2.500 2.500 0 0 0 5 0V3M7 11v10'/%3E%3Cpath d='M17.500 21V3c-2.500 1.500-3.500 4.500-3.500 8h3.500'/%3E%3C/svg%3E");
    --i-coffee: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4.500 8.500h11v6a4 4 0 0 1-4 4h-3a4 4 0 0 1-4-4z'/%3E%3Cpath d='M15.500 10h1.800a2.600 2.600 0 0 1 0 5.200h-1.800'/%3E%3Cpath d='M8 3.500v2.200M11.800 3.500v2.200'/%3E%3C/svg%3E");
    --i-fuel: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 20.500V5.500a2 2 0 0 1 2-2h6.500a2 2 0 0 1 2 2v15'/%3E%3Cpath d='M3.500 20.500h13'/%3E%3Cpath d='M7.500 7.500h5.500'/%3E%3Cpath d='M15.500 10.500h1.200a1.800 1.800 0 0 1 1.800 1.800V17a1.500 1.500 0 0 0 3 0V9.500L18.500 7'/%3E%3C/svg%3E");
    --i-pharmacy: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='4' width='16' height='16' rx='4.500'/%3E%3Cpath d='M12 8v8M8 12h8'/%3E%3C/svg%3E");
    --i-grocery: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.500 9.500h17l-1.700 9a2 2 0 0 1-2 1.500H7.200a2 2 0 0 1-2-1.500z'/%3E%3Cpath d='m8 9.500 3-5.500M16 9.500 13 4'/%3E%3C/svg%3E");
    --i-atm: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3.500' y='6' width='17' height='12' rx='2.500'/%3E%3Ccircle cx='12' cy='12' r='2.500'/%3E%3Cpath d='M6.500 9.500h.01M17.500 14.500h.01'/%3E%3C/svg%3E");
    --i-back: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m15 5-7 7 7 7'/%3E%3C/svg%3E");
    --i-pin: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s-6.5-5.4-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z'/%3E%3Ccircle cx='12' cy='10.5' r='2.3'/%3E%3C/svg%3E");
  }

  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

  html, body {
    margin: 0; padding: 0;
    position: fixed;            /* the document can never scroll or rubber-band under the sheet */
    top: 0; left: 0;
    overscroll-behavior: none;
    height: 100vh;
    height: 100dvh;
    width: 100vw;
    background: var(--basalt-950);
    color: var(--paper);
    font-family: 'Inter', sans-serif;
    overflow: hidden;
    touch-action: manipulation;
    -webkit-user-select: none; user-select: none;
    -webkit-touch-callout: none;
  }
  input { -webkit-user-select: text; user-select: text; }
  button { font-family: inherit; }
  .display { font-family: 'Space Grotesk', sans-serif; }
  .hidden { display: none !important; }

  /* Mask-based icon helper: any element with --icon set, or .has-ico (drawn by ::before) */
  .ico, .has-ico::before {
    content: "";
    display: inline-block;
    flex-shrink: 0;
    width: var(--ico-size, 24px);
    height: var(--ico-size, 24px);
    background-color: currentColor;
    -webkit-mask: var(--icon) center / contain no-repeat;
            mask: var(--icon) center / contain no-repeat;
  }

  /* Every tappable thing gives a little physical feedback */
  .press { transition: transform .15s var(--ease), background-color .15s; }
  .press:active { transform: scale(.97); }

  #app { position: relative; width: 100vw; height: 100vh; height: 100dvh; }

  /* ================= Bottom sheet ================= */
  #sidebar {
    position: absolute;
    left: 0; right: 0; bottom: 0;
    max-height: calc(100dvh - var(--safe-top) - 6px);
    background: var(--basalt-900);
    border-radius: var(--sheet-radius) var(--sheet-radius) 0 0;
    box-shadow: 0 -6px 20px rgba(0,0,0,.4);
    display: flex;
    flex-direction: column;
    z-index: 900;
    padding-bottom: var(--safe-bottom);
    transform: translateY(0);
    transition: transform .45s var(--ease-open);
  }
  #sidebar.mode-dest { max-height: calc(100dvh - var(--banner-h) - var(--safe-top) - 150px); }
  #sidebar.mode-dest #sidebar-scroll { overflow: hidden; flex: 0 1 auto; }
  #sidebar.mode-traffic { max-height: 50dvh; }
  /* Search: about half the screen, riding above the on-screen keyboard
     (--kb / --vvh are kept current from window.visualViewport by the script) */
  #sidebar.mode-search {
    bottom: max(var(--kb, 0px), var(--banner-h));
    height: min(50dvh, calc(var(--vvh, 100dvh) - var(--safe-top) - 12px));
  }

  /* Collapsed: handle + the Where to? pill peek out (88px must match setupSheetSwipe) */
  #sidebar.sheet-collapsed { transform: translateY(calc(100% - var(--peek) - var(--safe-bottom))); transition: transform .5s var(--ease-close); }
  #sidebar.dragging { transition: none !important; }
  /* closing for good: slide all the way down, THEN swap the content (so it never just vanishes) */
  #sidebar.sliding-out { transform: translateY(112%) !important; transition: transform .42s var(--ease-close) !important; }

  #mobile-sheet-handle {
    display: flex; align-items: center; justify-content: center;
    padding: 15px 0 12px;
    cursor: pointer;
    touch-action: none;
    flex-shrink: 0;
  }
  .handle-bar { width: 36px; height: 4px; background: #4b4e5c; border-radius: 2px; }

  #sidebar-scroll {
    overflow-y: auto;
    flex: 1;
    min-height: 0;
    padding: 0 16px 16px;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
  }
  #sidebar-scroll::-webkit-scrollbar { width: 0; }

  /* Row that rides above the sheet: locate (left), trip status (right) */
  .sheet-float {
    position: absolute;
    left: calc(14px + var(--safe-left));
    right: calc(14px + var(--safe-right));
    bottom: calc(100% + 12px);
    display: flex; align-items: flex-end; justify-content: flex-start; gap: 10px;
    pointer-events: none;
  }
  .sheet-float > * { pointer-events: auto; }

  #locate-btn {
    width: 52px; height: 52px;
    border-radius: 50%;
    border: none;
    background: var(--float-bg);
    color: var(--ui-icon);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
    cursor: pointer;
    flex-shrink: 0;
  }
  #locate-btn.busy .ico { animation: spin 1s linear infinite; }
  body.admin-on .sheet-float { left: calc(58px + var(--safe-left)); }     /* room for the admin toolbar column */

  .chip {
    height: 44px;
    border-radius: 16px;
    padding: 0 14px;
    display: flex; align-items: center; gap: 8px;
    background: var(--float-bg);
    border: none;
    color: var(--ui-text);
    font-size: 14px; font-weight: 600;
    white-space: nowrap;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
    cursor: pointer;
    animation: fadeUp .35s var(--ease) both;
  }

  /* ================= Location prompts ================= */
  :root { --banner-h: 0px; }
  body.loc-banner { --banner-h: calc(52px + var(--safe-bottom)); }
  /* the sheet rises above the bar so nothing is covered */
  #sidebar { bottom: max(var(--kb, 0px), var(--banner-h)); }
  body.loc-banner #sidebar { padding-bottom: 4px; }

  /* A slim strip, not a block: visible and one tap from fixed, but it never dominates the screen. */
  #loc-banner {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 920;
    height: var(--banner-h);
    padding: 7px 12px var(--safe-bottom);
    background: var(--apricot); color: var(--basalt-950);
    display: flex; align-items: center; gap: 10px;
    box-shadow: 0 -2px 10px rgba(0,0,0,.28);
    transform: translateY(110%);
    transition: transform .45s var(--ease);
  }
  body.loc-banner #loc-banner { transform: none; }
  .loc-banner-ico {
    width: 30px; height: 30px; border-radius: 10px; flex-shrink: 0;
    background: var(--basalt-950); color: var(--apricot);
    display: flex; align-items: center; justify-content: center;
  }
  .loc-banner-ico .ico { --ico-size: 17px; width: 17px; height: 17px; }
  .loc-banner-text { flex: 1; min-width: 0; line-height: 1.2; }
  .loc-banner-text b { display: block; font-size: 14px; font-weight: 700; }
  .loc-banner-text span { display: block; font-size: 11.5px; font-weight: 500; opacity: .8; margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #loc-banner-cta {
    border: none; border-radius: 11px; padding: 8px 14px; flex-shrink: 0;
    background: var(--basalt-950); color: var(--apricot);
    font-size: 13px; font-weight: 700; cursor: pointer;
  }

  /* the arrow button and the address header say "off" until it is fixed */
  #locate-btn.off { box-shadow: 0 0 0 1.5px rgba(245,165,54,.65), 0 4px 16px rgba(0,0,0,.4); animation: ringBtn 3s ease-out infinite; }
  #loc-chip.off .loc-label { color: var(--apricot); font-weight: 700; }
  #loc-chip.off .loc-label::before {
    content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--apricot); margin-right: 6px; vertical-align: 1px;
    animation: pulseDot 1.6s ease-out infinite;
  }

  /* "show me how" sheet */
  #loc-steps-scrim { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 941; opacity: 0; pointer-events: none; transition: opacity .5s var(--ease-close); }
  #loc-steps-scrim.open { opacity: 1; pointer-events: auto; transition: opacity .3s; }
  #loc-steps {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 951;
    background: var(--basalt-900); border-radius: var(--sheet-radius) var(--sheet-radius) 0 0;
    padding-bottom: calc(var(--safe-bottom) + 16px);
    transform: translateY(105%); transition: transform .5s var(--ease-close);
    max-height: 85dvh; overflow-y: auto;
  }
  #loc-steps.open { transform: none; transition: transform .42s var(--ease-open); }
  .steps-cta {
    display: block; width: calc(100% - 36px); margin: 6px 18px 0;
    border: none; border-radius: 16px; padding: 15px;
    background: var(--apricot); color: var(--basalt-950);
    font-size: 16px; font-weight: 700; cursor: pointer;
  }
  .steps-sub { margin: 0 18px 8px; font-size: 13px; color: var(--fog); }
  #loc-steps-list { margin: 4px 18px 12px; padding-left: 22px; font-size: 15px; line-height: 1.5; color: var(--paper); }
  #loc-steps-list li { padding: 5px 0 5px 4px; }
  #loc-steps-list li::marker { color: var(--apricot); font-weight: 700; }
  @media (min-width: 769px) { #loc-steps { left: 50%; right: auto; width: 440px; margin-left: -220px; } }

  /* ================= Home ================= */
  #search-bar-wrap { display: none; position: relative; }
  #sidebar.mode-search #search-bar-wrap { display: block; }

  #where-btn {
    display: none;
    width: 100%; height: 56px;
    border: none;
    border-radius: 20px;
    background: var(--basalt-800);
    color: var(--ui-text);
    align-items: center;
    padding: 0;
    overflow: hidden;
    cursor: pointer;
    font-size: 19px; font-weight: 600;
    position: relative;
  }
  #sidebar.mode-home #where-btn { display: flex; }
  .where-car { width: 78px; height: 56px; flex-shrink: 0; margin-left: -6px; padding: 10px 0 8px 0; color: var(--apricot); }
  .where-text { flex: 1; text-align: left; padding-left: 6px; }
  .where-go {
    position: relative;
    width: 56px; height: 56px;
    display: flex; align-items: center; justify-content: center;
    color: var(--ui-icon);
  }
  .where-go::before { content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 1px; background: rgba(255,255,255,.12); }
  .intro .where-go .ico { animation: nudgeRight 1.8s var(--ease) 1.2s 3; }
  /* a gentle ring on first load so the one thing to do is obvious */
  #where-btn::after {
    content: ""; position: absolute; inset: 0; border-radius: 20px;
    box-shadow: inset 0 0 0 0 rgba(245,165,54,.0);
    pointer-events: none;
  }

  .intro #where-btn::after { animation: ring 1.8s var(--ease) .8s 2; }

  /* Shortcut cards (home) / list rows (search): one element, two layouts */
  #presets { display: none; }
  #sidebar.mode-home #presets {
    display: flex; gap: 10px;
    overflow-x: auto;
    margin: 10px -16px 0;
    padding: 0 16px 2px;
    scroll-snap-type: x proximity;
    scroll-padding: 0 16px;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
  }
  #presets::-webkit-scrollbar { display: none; }

  .place {
    position: relative;
    flex: 0 0 108px;
    height: 112px;
    border: none;
    border-radius: 20px;
    background: var(--basalt-800);
    color: var(--ui-text);
    padding: 12px;
    display: flex;
    text-align: left;
    cursor: pointer;
    scroll-snap-align: start;
    animation: riseIn .5s var(--ease) both;
    animation-delay: calc(var(--i, 0) * 55ms + 60ms);
    --lv: var(--fog);
  }
  .place[data-level="easy"]     { --lv: var(--leaf); }
  .place[data-level="moderate"] { --lv: var(--apricot); }
  .place[data-level="tough"]    { --lv: var(--alert); }
  .place-cat { flex: 0 0 88px; flex-direction: column; justify-content: space-between; align-items: flex-start; background: var(--basalt-800); }
  .place-cat .ico { --ico-size: 30px; color: var(--apricot); }
  .place-cat .place-name { font-size: 15.5px; }
  .place-text { display: block; min-width: 0; }
  .place-name {
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    font-size: 16px; font-weight: 600; line-height: 1.18;
  }
  .place-sub { display: block; margin-top: 3px; font-size: 12.5px; font-weight: 500; color: var(--lv); }
  .place-car { position: absolute; left: 10px; bottom: 9px; width: 60px; height: 29px; color: var(--lv); }
  .place-recent {
    position: absolute; top: 11px; right: 10px;
    --ico-size: 14px; color: var(--fog); opacity: .8;
  }
  .place::before { display: none; }
  .places-label { display: none; }
  /* until the live outlook arrives */
  .place[data-level="loading"] .place-sub {
    width: 62px; height: 11px; border-radius: 6px; margin-top: 7px; color: transparent;
    background: linear-gradient(90deg, var(--basalt-700) 25%, #3d404c 50%, var(--basalt-700) 75%);
    background-size: 200% 100%; animation: shimmer 1.3s linear infinite;
  }

  /* Two status pills (Yandex Go's Delivery | Scooters row): live traffic + auto-parking */
  .status-row { display: none; gap: 10px; margin-top: 10px; }
  #sidebar.mode-home .status-row { display: flex; animation: riseIn .5s var(--ease) .35s both; }
  .status-pill {
    flex: 1; min-width: 0;
    height: 52px;
    border: none; border-radius: 18px;
    background: var(--basalt-800);
    color: var(--ui-text);
    display: flex; align-items: center; gap: 10px;
    padding: 0 12px;
    text-align: left;
    cursor: pointer;
  }
  .pill-text { min-width: 0; line-height: 1.15; }
  .pill-text b { display: block; font-size: 15px; font-weight: 600; }
  .pill-text small { display: block; font-size: 12px; color: var(--fog); margin-top: 1px; }
  /* One-at-a-time nudge: location permission, then install */
  #nudge-card {
    display: none;
    margin-top: 10px;
    padding: 12px;
    border-radius: 20px;
    background: var(--basalt-800);
    align-items: center; gap: 12px;
  }
  #nudge-card.show { display: flex; animation: riseIn .45s var(--ease) both; }
  #sidebar:not(.mode-home) #nudge-card { display: none; }
  .nudge-ico { width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0; background-size: 100% 100%; }
  .nudge-text { flex: 1; min-width: 0; }
  .nudge-text b { display: block; font-size: 15px; font-weight: 600; }
  .nudge-text span { display: block; font-size: 12.5px; color: var(--fog); margin-top: 2px; line-height: 1.35; }
  .nudge-actions { display: flex; flex-direction: column; gap: 4px; align-items: stretch; }
  #nudge-cta {
    border: none; border-radius: 12px; padding: 10px 14px;
    background: var(--apricot); color: var(--basalt-950);
    font-size: 14px; font-weight: 700; cursor: pointer;
  }
  #nudge-dismiss {
    border: none; background: none; color: var(--fog);
    font-size: 12px; padding: 4px; cursor: pointer;
  }

  /* ================= Search ================= */
  .sheet-search-row { display: flex; align-items: center; gap: 8px; }
  #search-close-btn {
    width: 40px; height: 44px; flex-shrink: 0;
    border: none; background: none; color: var(--ui-icon);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; margin-left: -8px;
  }
  #search-close-btn .ico { transform: rotate(180deg); }
  .search-input-box {
    flex: 1; min-width: 0;
    display: flex; align-items: center;
    height: 48px;
    background: var(--basalt-950);
    border-radius: 16px;
    padding: 0 4px 0 14px;
    box-shadow: inset 0 0 0 1px transparent;
    transition: box-shadow .2s;
  }
  .search-input-box:focus-within { box-shadow: inset 0 0 0 1px var(--apricot-dim); }
  #search-input {
    flex: 1; min-width: 0; height: 100%;
    background: transparent; border: none; outline: none;
    color: var(--ui-text);
    caret-color: var(--apricot);
    font-family: 'Inter', sans-serif;
    font-size: 17px; /* >=16px prevents iOS auto-zoom */
  }
  #search-input::placeholder { color: var(--fog); }
  .search-clear-btn {
    background: transparent; border: none; color: var(--fog);
    font-size: 22px; cursor: pointer; padding: 0 10px; line-height: 1;
    display: flex; align-items: center; justify-content: center;
    min-height: 44px; min-width: 40px;
  }

  .search-dropdown { margin-top: 6px; }
  #sidebar:not(.mode-search) #search-dropdown { display: none; }
  .search-item {
    display: flex; align-items: center; gap: 14px;
    padding: 10px 0; min-height: 62px;
    border-bottom: 1px solid rgba(58,61,74,.55);
    cursor: pointer;
    animation: fadeUp .28s var(--ease) both;
  }
  .search-item:last-child { border-bottom: none; }
  .search-item:active { background: rgba(255,255,255,.03); }
  .search-item-ico { width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0; background-size: 100% 100%; }
  .search-item-text { flex: 1; min-width: 0; }
  .search-item-title { font-size: 16.5px; font-weight: 500; color: var(--ui-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .search-item-sub { font-size: 13px; color: var(--fog); margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .search-item-dist { font-size: 13px; color: var(--fog); flex-shrink: 0; }
  .search-no-results { padding: 26px 8px; font-size: 14px; color: var(--fog); text-align: center; }

  /* Landmarks / recents as a list while searching */
  #sidebar.mode-search #presets { display: block; margin-top: 4px; }
  #sidebar.mode-search .places-label {
    display: block; margin: 14px 0 2px;
    font-size: 13px; font-weight: 600; color: var(--fog);
  }
  #sidebar.mode-search .place {
    display: flex; align-items: center; gap: 14px;
    width: 100%; height: auto; min-height: 62px;
    padding: 10px 0;
    border-radius: 0; background: transparent;
    border-bottom: 1px solid rgba(58,61,74,.55);
    scroll-snap-align: none;
  }
  #sidebar.mode-search .place::before {
    display: block; content: "";
    width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0;
    background-size: 100% 100%;
  }
  #sidebar.mode-search .place-text { flex: 1; }
  #sidebar.mode-search .place-name { display: block; font-size: 16.5px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #sidebar.mode-search .place-car { position: static; width: 46px; height: 22px; flex-shrink: 0; }
  #sidebar.mode-search .place-recent { display: none; }
  .sheet-note { display: none; font-size: 12.5px; color: var(--fog); line-height: 1.5; padding: 10px 2px 0; }
  #sidebar.mode-search .sheet-note { display: block; }

  /* While live results are on screen they replace the shortcuts */
  #search-bar-wrap:has(#search-dropdown:not(.hidden)) ~ #presets,
  #search-bar-wrap:has(#search-dropdown:not(.hidden)) ~ .sheet-note { display: none !important; }

  /* ================= Destination + recommendations ================= */
  #dest-pane, #traffic-pane { display: none; }
  #sidebar.mode-dest #dest-pane { display: block; animation: paneIn .38s var(--ease) both; }
  #sidebar.mode-traffic #traffic-pane { display: block; animation: paneIn .38s var(--ease) both; }

  #destination-active {
    position: relative;
    display: none;
    align-items: center; gap: 12px;
    padding: 4px 0 8px;
  }
  .dest-text { flex: 1; min-width: 0; cursor: pointer; }
  .dest-title {
    font-size: 21px; font-weight: 700; line-height: 1.2;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .dest-sub { font-size: 13px; color: var(--fog); margin-top: 2px; }
  .round-btn {
    width: 36px; height: 36px; border-radius: 50%;
    border: none; flex-shrink: 0;
    background: var(--basalt-700); color: var(--ui-text);
    font-size: 20px; line-height: 1; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
  }

  .rec-card {
    position: relative;
    display: flex; align-items: center; gap: 12px;
    padding: 12px;
    margin: 4px 0;
    border: 1px solid transparent;
    border-radius: 20px;
    background: transparent;
    cursor: pointer;
    transition: background-color .25s, border-color .25s;
    animation: riseIn .45s var(--ease) both;
  }
  .rec-card:nth-child(2) { animation-delay: .06s; }
  .rec-card:nth-child(3) { animation-delay: .12s; }
  .rec-card:active { background: rgba(255,255,255,.03); }
  /* the highlighted (yellow) card is the one that is selected: #1 to begin with, then whichever is tapped */
  .rec-card.selected { border-color: var(--apricot-dim); background: rgba(245,165,54,.07); }
  /* ...but the "Best match" tag always stays on the best (first) option */
  .rec-card:first-child { margin-top: 16px; }
  .rec-card:first-child::before {
    content: "Best match";
    position: absolute; top: -9px; left: 14px;
    background: var(--apricot); color: var(--basalt-950);
    font-size: 11px; font-weight: 700; letter-spacing: .02em;
    padding: 2px 9px; border-radius: 8px;
  }
  .rec-rank {
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 17px;
    color: var(--ui-text); background: rgba(245,165,54,.15);
    width: 40px; height: 40px; border-radius: 12px;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  }
  .rec-card.selected .rec-rank { background: var(--apricot); color: var(--basalt-950); }
  .rec-body { flex: 1; min-width: 0; }
  .rec-name { font-size: 16.5px; font-weight: 600; color: var(--ui-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .rec-meta { font-size: 13px; color: var(--fog); margin-top: 3px; display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .gauge { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .gauge-inner {
    width: 33px; height: 33px; border-radius: 50%; background: var(--basalt-900);
    display: flex; align-items: center; justify-content: center;
    font-family: 'Space Grotesk', sans-serif; font-size: 10.5px; font-weight: 700; color: var(--ui-text);
  }
  .rec-card.selected .gauge-inner { background: #231f1a; }
  .pill { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 20px; }
  .pill-free   { background: rgba(52,199,123,.15); color: var(--leaf); }
  .pill-paid   { background: rgba(226,87,76,.15); color: var(--alert); }
  .pill-lot    { background: rgba(77,143,240,.15); color: var(--sapphire); }
  .pill-unavailable { background: rgba(243,156,18,.15); color: var(--unavailable); }
  .pill-unspecified { background: rgba(148,152,166,.15); color: var(--fog); }
  #rec-empty { font-size: 14px; color: var(--fog); text-align: center; padding: 24px 8px; line-height: 1.6; }

  /* loading placeholders while recommendations are on their way */
  .rec-skel { display: flex; align-items: center; gap: 12px; padding: 12px 0; }
  .rec-skel i, .rec-skel b, .rec-skel u {
    display: block; border-radius: 10px; text-decoration: none;
    background: linear-gradient(90deg, var(--basalt-800) 25%, #30333f 50%, var(--basalt-800) 75%);
    background-size: 200% 100%; animation: shimmer 1.3s linear infinite;
  }
  .rec-skel i { width: 40px; height: 40px; }
  .rec-skel b { flex: 1; height: 38px; }
  .rec-skel u { width: 44px; height: 44px; border-radius: 50%; }

  @media (max-width: 768px) and (max-height: 660px) {
    body #snack, body #parked-toast { left: calc(76px + var(--safe-left)); max-height: 58px; overflow: hidden; }   /* (body prefix: this block sits before the base rule) */
    #sidebar.mode-dest #home-btn { display: none; }
  }
  /* very short phones (about iPhone SE): trim the extras so all three spots and the button still fit without scrolling */
  @media (max-height: 600px) {
    #rec-legend { display: none; }
    #go-btn { height: 46px; }
    #go-bar { padding: 4px 16px calc(var(--safe-bottom) + 10px); }
    #mobile-sheet-handle { padding: 9px 0 8px; }
  }

  /* ================= Traffic ================= */
  .pane-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 4px 0 6px; }
  .pane-head .dest-title { font-size: 21px; }
  .overall-level { font-family: 'Space Grotesk', sans-serif; font-size: 18px; font-weight: 700; margin-right: 4px; }
  .traffic-card {
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 0; border-bottom: 1px solid rgba(58,61,74,.55); font-size: 16px;
    animation: fadeUp .3s var(--ease) both;
  }
  .traffic-card:last-child { border-bottom: none; }
  .traffic-name { color: var(--ui-text); font-weight: 500; }
  .traffic-badge { font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 20px; }
  .badge-Low    { background: rgba(52,199,123,.15); color: var(--leaf); }
  .badge-Medium { background: rgba(245,165,54,.15); color: var(--apricot); }
  .badge-Heavy  { background: rgba(226,87,76,.15); color: var(--alert); }
  .muted { font-size: 12.5px; color: var(--fog); }

  /* Circular 0-10 live-traffic score */
  .traffic-score {
    display: inline-flex; align-items: center; justify-content: center;
    width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
    font-family: 'Space Grotesk', sans-serif; font-size: 15px; font-weight: 700;
    color: var(--basalt-950); background: var(--leaf);
    box-shadow: 0 0 0 3px rgba(148,152,166,.2);
    transition: background-color .4s;
  }
  .traffic-score.lvl-Medium { background: var(--apricot); }
  .traffic-score.lvl-Heavy  { background: var(--alert); color: var(--paper); }

  /* ================= Map + overlays ================= */
  #map-wrap { position: absolute; inset: 0; }
  #map {
    position: relative; z-index: 0; /* contains Leaflet's z-indexes so overlays always sit above */
    height: 100%; width: 100%; background: #1b2030;
  }
  /* The dark navy map is baked into each tile when it loads (DarkOSMLayer in the script):
     a CSS filter on the whole tile pane was re-run every frame of a zoom on iOS. */

  .fab {
    position: absolute; z-index: 750;
    width: 46px; height: 46px; border-radius: 50%;
    border: none; padding: 0;
    background: var(--float-bg); color: var(--ui-icon);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
    overflow: hidden;
  }
  #menu-btn   { top: calc(var(--safe-top) + 8px); left: calc(14px + var(--safe-left)); }
  #menu-btn img { width: 100%; height: 100%; display: block; }
  #layers-btn { top: calc(var(--safe-top) + 8px); right: calc(14px + var(--safe-right)); }
  #traffic-badge { top: calc(var(--safe-top) + 62px); right: calc(14px + var(--safe-right)); }

  /* "Your location >  Street" (Yandex Go's address header) */
  #loc-chip {
    position: absolute; z-index: 700;
    top: calc(var(--safe-top) + 6px); left: 50%; transform: translateX(-50%);
    max-width: calc(100% - 140px);
    border: none; background: none; cursor: pointer;
    text-align: center; color: var(--ui-text);
    text-shadow: 0 1px 6px rgba(0,0,0,.95), 0 0 2px rgba(0,0,0,.9);
    padding: 2px 8px;
  }
  .loc-label { display: block; font-size: 12.5px; font-weight: 500; white-space: nowrap; }
  #loc-street {
    display: block; margin-top: 1px;
    font-size: 19px; font-weight: 700; line-height: 1.2;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    transition: opacity .25s;
  }
  #loc-street.swap { opacity: 0; }

  /* Zoom buttons only where there is no pinch-zoom */
  .leaflet-control-container .leaflet-bottom.leaflet-right {
    bottom: auto;
    top: clamp(132px, 40%, calc(100% - 440px));       /* never lower than the sheet allows on a short screen */
    right: calc(14px + var(--safe-right));
    transition: top .25s;
  }
  @media (max-width: 768px) {
    /* phone layout: the sheet is tall in these modes, so the zoom buttons move up under the legend button */
    body:not([data-sheet="home"]) .leaflet-control-container .leaflet-bottom.leaflet-right { top: calc(var(--safe-top) + 124px); }
  }
  .leaflet-control-container .leaflet-bottom.leaflet-right .leaflet-control { margin: 0; }
  .leaflet-control-zoom {
    display: flex; flex-direction: column; gap: 10px;
    border: none !important; box-shadow: none !important; background: none !important;
  }
  .leaflet-control-container .leaflet-control-zoom a {
    width: 44px !important; height: 44px !important; line-height: 40px !important;
    border-radius: 14px !important; border: none !important;
    background: var(--float-bg); color: var(--ui-icon);
    font-family: 'Inter', sans-serif; font-size: 28px; font-weight: 300;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
  }
  .leaflet-control-container .leaflet-control-zoom a:hover { background: var(--basalt-800); color: var(--ui-icon); }
  @media (pointer: coarse) { .leaflet-control-zoom { display: none; } }

  /* OpenStreetMap attribution must stay visible, so it sits under the logo button */
  .leaflet-control-container .leaflet-bottom.leaflet-left {
    bottom: auto; top: calc(var(--safe-top) + 58px); left: calc(8px + var(--safe-left)); right: calc(68px + var(--safe-right));
  }
  .leaflet-control-attribution {
    background: rgba(20,21,26,.72) !important; color: var(--fog) !important;
    font-size: 10px; border-radius: 8px; padding: 1px 7px !important;
  }
  .leaflet-control-attribution a { color: var(--fog) !important; }

  /* Curation (Geoman) toolbar on the left, clear of the right-hand buttons */
  .leaflet-control-container .leaflet-top { top: calc(var(--safe-top) + 96px); }
  .leaflet-control-container .leaflet-left { left: var(--safe-left); }
  /* Popups (segments, recommendation pins, "your location"): app colours, small, no big tip */
  .leaflet-popup.pk-popup .leaflet-popup-content-wrapper {
    background: var(--basalt-900); color: var(--paper);
    border-radius: 14px; padding: 0;
    box-shadow: 0 4px 16px rgba(0,0,0,.5); border: 1px solid rgba(255,255,255,.07);
  }
  .leaflet-popup.pk-popup .leaflet-popup-content {
    margin: 8px 11px; max-width: 200px;     /* Leaflet measures the text and sets the width (capped) */
    font-family: 'Inter', sans-serif; font-size: 12px; line-height: 1.4;
  }
  .leaflet-popup.pk-popup .leaflet-popup-tip { background: var(--basalt-900); width: 12px; height: 12px; margin: -6px auto 0; box-shadow: none; }
  .leaflet-popup.pk-popup .leaflet-popup-tip-container { width: 24px; height: 12px; }
  /* the templates carry inline dark-on-white colours: override them */
  .leaflet-popup.pk-popup .leaflet-popup-content * { color: var(--fog) !important; font-size: 12px !important; }
  .leaflet-popup.pk-popup .leaflet-popup-content strong { color: var(--paper) !important; font-size: 13px !important; font-weight: 600; }
  .leaflet-popup.pk-popup .leaflet-popup-content b { color: var(--paper) !important; font-weight: 600; }
  .pk-pop-row { margin-top: 2px; }
  .leaflet-fade-anim .leaflet-popup { transition: none; }


  /* One-time coachmark instead of a permanent banner */
  #hint-banner {
    position: absolute; z-index: 500;
    top: calc(var(--safe-top) + 74px); left: 50%;
    transform: translate(-50%, -8px);
    background: var(--float-bg); color: var(--ui-text);
    border-radius: 999px; padding: 8px 14px;
    font-size: 12.5px; font-weight: 500;
    display: flex; align-items: center; gap: 8px;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
    opacity: 0; pointer-events: none;
    transition: opacity .35s, transform .35s var(--ease);
    max-width: calc(100% - 150px); white-space: nowrap;
  }
  #hint-banner.show { opacity: 1; transform: translate(-50%, 0); }
  #hint-banner .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--apricot); flex-shrink: 0; }

  /* Destination callout (Yandex Go's "Pickup ~3 min" card) */
  .dest-callout-wrap { width: 0; height: 0; }
  .dest-callout {
    position: absolute; bottom: 22px; left: 0; transform: translateX(-50%);
    display: flex; align-items: center; gap: 9px;
    padding: 7px 14px 7px 7px;
    background: var(--basalt-900); color: var(--ui-text);
    border-radius: 16px; white-space: nowrap;
    box-shadow: 0 6px 20px rgba(0,0,0,.5);
    animation: dropIn .5s var(--ease) both;
  }
  .dc-ico { width: 34px; height: 34px; border-radius: 11px; flex-shrink: 0; background-size: 100% 100%; }
  .dc-text b { display: block; max-width: 150px; overflow: hidden; text-overflow: ellipsis; font-size: 14px; font-weight: 700; line-height: 1.15; }
  .dc-text span { display: block; font-size: 12px; color: var(--fog); margin-top: 1px; }
  .dc-stem { position: absolute; left: -1px; bottom: 6px; width: 2px; height: 16px; background: var(--paper); border-radius: 1px; }
  .dc-dot {
    position: absolute; left: -7px; bottom: -1px; width: 14px; height: 14px; border-radius: 50%;
    background: var(--sapphire); border: 3px solid var(--paper); box-shadow: 0 0 0 4px rgba(77,143,240,.25);
  }

  .rec-marker {
    background: var(--apricot); color: var(--basalt-950);
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 13px;
    width: 26px; height: 26px;
    border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 3px 10px rgba(0,0,0,.4); border: 2px solid var(--basalt-950);
    animation: popIn .45s var(--ease) both;
  }
  .rec-marker-wrap:nth-child(2) .rec-marker { animation-delay: .08s; }
  .rec-marker span { transform: rotate(45deg); }
  .rec-marker-wrap.selected .rec-marker { border-color: var(--paper); box-shadow: 0 0 0 3px rgba(245,165,54,.35), 0 3px 10px rgba(0,0,0,.4); }

  /* Live GPS user-location marker */
  .user-marker-wrap { position: relative; }
  .user-location-marker {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 16px; height: 16px; background: var(--leaf);
    border: 3px solid var(--paper); border-radius: 50%;
    box-shadow: 0 0 0 4px rgba(52,199,123,.25); z-index: 2;
  }
  .user-location-pulse {
    position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
    width: 16px; height: 16px; background: rgba(52,199,123,.45); border-radius: 50%;
    animation: user-pulse 2.2s infinite; z-index: 1;
  }
  .live-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--leaf); animation: pulse 2s infinite; flex-shrink: 0; }

  /* ================= Toasts ================= */
  #parked-toast, #snack {
    position: absolute; z-index: 780;
    top: calc(var(--safe-top) + 84px);
    left: calc(14px + var(--safe-left)); right: calc(70px + var(--safe-right));      /* clear of the corner badge column */
    display: flex; align-items: center; gap: 12px;
    padding: 10px 10px 10px 12px;
    background: var(--float-bg); border-radius: 18px;
    box-shadow: 0 8px 28px rgba(0,0,0,.55);
    opacity: 0; transform: translateY(-12px) scale(.98);
    pointer-events: none;
    transition: opacity .3s, transform .4s var(--ease);
  }
  #parked-toast.show, #snack.show { opacity: 1; transform: none; pointer-events: auto; }
  #snack { justify-content: center; font-size: 14px; font-weight: 500; padding: 14px; }
  .toast-ico { width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0; background-size: 100% 100%; }
  .toast-text { flex: 1; min-width: 0; }
  .toast-title { font-size: 15px; font-weight: 600; line-height: 1.25; color: var(--ui-text); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .toast-sub { font-size: 12px; color: var(--fog); margin-top: 2px; }
  #toast-undo {
    border: none; background: var(--basalt-700); color: var(--ui-text);
    border-radius: 12px; padding: 10px 14px; font-size: 14px; font-weight: 600; cursor: pointer; flex-shrink: 0;
  }

  /* ================= Legend sheet + menu ================= */
  #layers-scrim, #menu-scrim {
    position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 940;
    opacity: 0; pointer-events: none; transition: opacity .5s var(--ease-close);
  }
  #layers-scrim.open, #menu-scrim.open { opacity: 1; pointer-events: auto; transition: opacity .3s; }

  #layers-sheet {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 950;
    max-height: 82dvh; overflow-y: auto;
    background: var(--basalt-900);
    border-radius: var(--sheet-radius) var(--sheet-radius) 0 0;
    padding-bottom: calc(var(--safe-bottom) + 12px);
    box-shadow: 0 -8px 32px rgba(0,0,0,.5);
    transform: translateY(105%);
    transition: transform .5s var(--ease-close);
  }
  #layers-sheet.open { transform: translateY(0); transition: transform .42s var(--ease-open); }
  .layers-title { padding: 4px 18px 8px; font-size: 21px; font-weight: 700; color: var(--ui-text); }
  .layer-row {
    display: flex; align-items: center; gap: 16px;
    padding: 11px 18px; width: 100%;
    font-size: 17px; color: var(--ui-text);
    background: none; border: none; text-align: left; cursor: default;
  }
  button.layer-row { cursor: pointer; }
  .layer-ico {
    width: 40px; height: 40px; border-radius: 12px; background: var(--basalt-950);
    display: flex; align-items: center; justify-content: center; flex-shrink: 0; color: var(--ui-icon);
  }
  .layer-name { flex: 1; min-width: 0; }
  .swatch { width: 22px; height: 4px; border-radius: 2px; flex-shrink: 0; }
  .seg-toggle { cursor: pointer; border-bottom: 1px solid rgba(58,61,74,.55); margin-bottom: 4px; padding-bottom: 14px; }
  #legend .legend-row { transition: opacity .25s; }
  #legend.dim .legend-row { opacity: .4; }

  /* On / off switch */
  .switch {
    margin-left: auto; width: 46px; height: 28px; border-radius: 14px;
    background: var(--basalt-700); position: relative; flex-shrink: 0; transition: background .25s;
  }
  .switch::after {
    content: ""; position: absolute; top: 3px; left: 3px; width: 22px; height: 22px; border-radius: 50%;
    background: var(--paper); transition: transform .25s var(--ease);
  }
  [aria-checked="true"] > .switch { background: var(--apricot); }
  [aria-checked="true"] > .switch::after { transform: translateX(18px); }


  #menu-drawer {
    position: fixed; top: 0; bottom: 0; left: 0;
    width: min(86vw, 340px); z-index: 960; overflow-y: auto;
    background: var(--basalt-900);
    padding: calc(var(--safe-top) + 24px) 4px calc(var(--safe-bottom) + 16px);
    box-shadow: 8px 0 32px rgba(0,0,0,.5);
    transform: translateX(-105%);
    transition: transform .5s var(--ease-close);
  }
  #menu-drawer.open { transform: translateX(0); }
  .brand { padding: 0 18px 18px; margin-bottom: 8px; border-bottom: 1px solid rgba(58,61,74,.7); }
  .brand-logo { width: 56px; height: 56px; border-radius: 16px; display: block; margin-bottom: 14px; }
  .brand h1 { font-size: 24px; margin: 0; font-weight: 700; color: var(--ui-text); }
  .brand p { margin: 6px 0 0; font-size: 14px; color: var(--fog); line-height: 1.5; }
  .menu-copy { padding: 6px 18px 10px; }
  .menu-copy h2 { font-size: 15px; font-weight: 600; margin: 8px 0 4px; color: var(--ui-text); }
  .menu-copy p { margin: 0; font-size: 13px; color: var(--fog); line-height: 1.55; }
  .d-row { cursor: pointer; }
  .d-row:active { background: rgba(255,255,255,.04); }
  .layer-name small { display: block; font-size: 12px; color: var(--fog); margin-top: 1px; }
  #auto-park-toggle[aria-checked="true"] #auto-park-state { color: var(--leaf); }
  #auto-park-toggle[aria-checked="false"]::before { filter: grayscale(1); opacity: .7; }
  .d-row::before { content: ""; width: 40px; height: 40px; flex-shrink: 0; border-radius: 12px; background-size: 100% 100%; }
  #admin-toggle.active { background: rgba(245,165,54,.12); }
  .menu-foot { padding: 14px 18px 0; font-size: 12px; color: var(--fog); display: flex; align-items: center; gap: 8px; }

  /* ================= Modals ================= */
  #modal-backdrop {
    position: fixed; inset: 0; background: rgba(0,0,0,.55);
    z-index: 999; /* above the sheet + buttons, just below the modals at 1000 */
    animation: fadeIn .25s both;
  }
  #admin-modal, #admin-login-modal {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
    z-index: 1000; width: min(92vw, 360px); max-height: 88dvh; overflow-y: auto;
    background: var(--basalt-900); padding: 22px 20px 20px; border-radius: 28px;
    box-shadow: 0 16px 48px rgba(0,0,0,.75);
    animation: modalIn .35s var(--ease) both;
  }
  #admin-modal h3, #admin-login-modal h3 { margin: 0 0 14px; font-size: 20px; font-weight: 600; color: var(--ui-text); }
  .admin-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
  .admin-field label { font-size: 13px; font-weight: 500; color: var(--fog); }
  .admin-field input, .admin-field select {
    background: var(--basalt-950); border: 1px solid transparent; color: var(--ui-text);
    padding: 10px 12px; border-radius: 14px; font-family: 'Inter', sans-serif; font-size: 16px; min-height: 48px;
  }
  .admin-field input:focus, .admin-field select:focus { outline: none; border-color: var(--apricot-dim); }
  .admin-actions { display: flex; gap: 8px; margin-top: 16px; }
  .btn-save, .btn-delete, .btn-cancel { flex: 1; font-weight: 600; padding: 10px; border-radius: 14px; cursor: pointer; font-size: 14px; min-height: 48px; border: none; }
  .btn-save   { background: var(--apricot); color: var(--basalt-950); }
  .btn-delete { background: rgba(226,87,76,.18); color: var(--alert); }
  .btn-cancel { background: var(--basalt-800); color: var(--fog); }

  /* ================= Yandex live-traffic view ================= */
  #ytraffic { position: fixed; inset: 0; z-index: 935; background: #1b1d24; display: none; }
  #ytraffic.open { display: block; animation: fadeIn .25s both; }
  .yt-frame, .yt-frame iframe { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
  .yt-bar {
    position: absolute; z-index: 2;
    top: calc(var(--safe-top) + 10px); left: calc(12px + var(--safe-left));
    display: flex; align-items: center; gap: 10px;
    background: var(--float-bg); border-radius: 20px; padding: 6px 16px 6px 6px;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
  }
  .yt-title { line-height: 1.2; }
  .yt-title b { display: block; font-size: 14px; font-weight: 700; }
  .yt-title span { display: block; font-size: 12px; color: var(--fog); }
  #yt-error {
    display: none; position: absolute; inset: 0; z-index: 3;
    flex-direction: column; align-items: center; justify-content: center; gap: 6px;
    text-align: center; padding: 28px; background: var(--basalt-900);
  }
  #yt-error.show { display: flex; }
  #yt-error b { font-size: 18px; }
  #yt-error p { margin: 0 0 14px; font-size: 14px; color: var(--fog); max-width: 320px; line-height: 1.5; }

  /* ================= Start screen ================= */
  #landing {
    position: fixed; inset: 0; z-index: 895;
    display: flex; flex-direction: column;
    padding-top: calc(var(--safe-top) + 8px);
    padding-bottom: var(--banner-h);                   /* the content scrolls above the location bar, never under it */
    background:
      radial-gradient(130% 52% at 50% -10%, rgba(245,165,54,.11), transparent 62%),
      var(--basalt-950);
    transition: opacity .28s var(--ease), transform .28s var(--ease);
  }
  body[data-screen="map"] #landing {
    opacity: 0; transform: scale(1.02); visibility: hidden; pointer-events: none;
    transition: opacity .28s var(--ease), transform .28s var(--ease), visibility 0s .28s;
  }
  body.no-anim #landing, body.no-anim #sidebar { transition: none !important; }
  .ld-top {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-shrink: 0;
    height: 56px; padding: 0 calc(14px + var(--safe-right)) 0 calc(14px + var(--safe-left));
  }
  .ld-top .fab { position: static; flex-shrink: 0; }
  .ld-top .fab img { width: 100%; height: 100%; display: block; }
  #ld-where {
    flex: 1; min-width: 0; border: none; background: none; cursor: pointer;
    text-align: center; color: var(--ui-text); padding: 2px 6px;
  }
  .ld-where-top { display: block; font-size: 12.5px; font-weight: 500; white-space: nowrap; }
  #ld-street { display: block; margin-top: 1px; font-size: 19px; font-weight: 700; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  #ld-where.off .ld-where-top::before {
    content: ""; display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: var(--apricot); margin-right: 6px; vertical-align: 1px; animation: pulseDot 1.6s ease-out infinite;
  }
  .ld-main {
    flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch;
    width: 100%; max-width: 560px; margin: 0 auto;
    padding: 0 calc(18px + var(--safe-right)) calc(var(--safe-bottom) + 28px) calc(18px + var(--safe-left));
  }
  .ld-main::-webkit-scrollbar { width: 0; }
  .ld-title {
    margin: clamp(22px, 8vh, 72px) 2px 20px;
    font-family: 'Space Grotesk', sans-serif; font-weight: 700; letter-spacing: -.01em;
    font-size: clamp(30px, 8.6vw, 40px); line-height: 1.1; color: var(--ui-text);
  }
  .ld-search {
    display: flex; align-items: center; height: 62px; padding: 0 11px 0 6px;
    background: var(--basalt-800); border-radius: 22px; box-shadow: 0 8px 28px rgba(0,0,0,.38);
  }
  .ld-bar {
    flex: 1; min-width: 0; height: 100%; display: flex; align-items: center; gap: 10px;
    padding: 0 6px 0 14px; border: none; background: none; color: var(--ui-text); cursor: pointer; border-radius: 18px;
  }
  .ld-bar .ico { --ico-size: 24px; color: var(--paper); }
  .ld-bar-text { flex: 1; text-align: center; font-size: 19px; font-weight: 700; padding-right: 24px; }
  .ld-map {
    width: 42px; height: 42px; flex-shrink: 0; border-radius: 50%; border: none; cursor: pointer;
    background: var(--paper); color: var(--basalt-950); display: flex; align-items: center; justify-content: center;
  }
  .ld-map .ico { --ico-size: 21px; }
  .ld-cats { display: flex; justify-content: space-between; gap: 8px; margin: 26px 0 8px; }
  .ld-cat {
    flex: 1; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 8px;
    border: none; background: none; color: var(--ui-text); font-size: 12.5px; font-weight: 600; cursor: pointer; padding: 0;
  }
  .ld-cat-ico {
    width: 100%; max-width: 64px; aspect-ratio: 1; border-radius: 20px; background: var(--basalt-800); color: var(--apricot);
    display: flex; align-items: center; justify-content: center; transition: background-color .15s;
  }
  .ld-cat-ico .ico { --ico-size: 28px; }
  .ld-list { margin-top: 14px; }
  .ld-list .search-item { min-height: 66px; animation: none; }
  .ld-list .search-item:last-child { border-bottom: none; }

  /* ================= Search page ================= */
  #search-page {
    position: fixed; left: 0; right: 0; top: var(--vvt, 0px); height: var(--vvh, 100dvh);
    z-index: 915; display: flex; flex-direction: column;
    padding-top: var(--safe-top);
    background: var(--basalt-950);
    transform: translateY(100%); visibility: hidden;
    transition: transform .45s var(--ease-close), visibility 0s .45s;
    will-change: transform;
  }
  #search-page.open { transform: none; visibility: visible; transition: transform .32s var(--ease-open); }
  #search-page.dragging { transition: none; }
  .sp-grip { display: flex; justify-content: center; padding: 8px 0 0; flex-shrink: 0; }
  .sp-head { display: flex; align-items: center; gap: 6px; padding: 6px 14px 10px; flex-shrink: 0; }
  #search-close-btn .ico { transform: none; }
  #sp-chips { display: flex; gap: 8px; overflow-x: auto; padding: 0 14px 10px; flex-shrink: 0; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
  #sp-chips::-webkit-scrollbar { display: none; }
  .sp-chip {
    display: flex; align-items: center; gap: 7px; flex-shrink: 0; height: 38px; padding: 0 14px;
    border: none; border-radius: 19px; background: var(--basalt-800); color: var(--ui-text);
    font-size: 14px; font-weight: 600; white-space: nowrap; cursor: pointer;
  }
  .sp-chip .ico { --ico-size: 18px; color: var(--apricot); }
  #sp-body {
    flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch;
    padding: 2px 14px calc(var(--safe-bottom) + 28px);
  }
  #sp-body::-webkit-scrollbar { width: 0; }
  #search-page.has-query #sp-suggest { display: none; }
  #search-page:not(.has-query) #search-dropdown, #search-page:not(.has-query) #sp-note { display: none !important; }
  .search-dropdown { margin-top: 0; }
  #sp-note { font-size: 13px; color: var(--fog); padding: 4px 4px 10px; line-height: 1.4; }
  .sp-label { font-size: 13px; font-weight: 600; color: var(--fog); margin: 8px 4px 0; }
  .search-item-end { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; }
  .search-item-open { font-size: 11.5px; font-weight: 600; }
  .search-item-open.yes { color: var(--leaf); }
  .search-item-open.no { color: var(--alert); }
  .sp-skel { height: 62px; display: flex; align-items: center; gap: 14px; }
  .sp-skel i { width: 40px; height: 40px; border-radius: 12px; background: var(--basalt-800); }
  .sp-skel b { flex: 1; height: 14px; border-radius: 7px; background: var(--basalt-800); max-width: 60%; }
  .search-item[data-level="easy"] .search-item-dist { color: var(--leaf); }
  .search-item[data-level="moderate"] .search-item-dist { color: var(--apricot); }
  .search-item[data-level="tough"] .search-item-dist { color: var(--alert); }

  /* the location bar never sits on top of the keyboard area */
  body.search-open #loc-banner { display: none; }

  /* ================= Traffic badge (top-right corner) ================= */
  .traffic-badge { overflow: visible; }
  .traffic-badge .traffic-score { width: 32px; height: 32px; }

  /* ================= Destination: caption, the Let's go bar ================= */
  #rec-legend { text-align: right; font-size: 11px; font-weight: 500; color: var(--fog); opacity: .6; padding: 0 4px 4px; letter-spacing: .01em; }
  #rec-legend:has(+ #rec-list #rec-empty) { display: none; }
  .rec-card { cursor: pointer; }
  @media (max-height: 740px) {
    .rec-card { padding: 7px 10px; margin: 2px 0; }
    .rec-rank { width: 34px; height: 34px; font-size: 15px; }
    .rec-name { font-size: 15.5px; }
    .rec-meta { margin-top: 1px; }
    .gauge { width: 40px; height: 40px; } .gauge-inner { width: 30px; height: 30px; }
    #go-btn { height: 50px; }
    #go-bar { padding-top: 6px; }
  }
  #go-bar { flex-shrink: 0; padding: 10px 16px calc(var(--safe-bottom) + 14px); background: var(--basalt-900); box-shadow: 0 -10px 18px rgba(20,21,26,.55); }
  #sidebar:not(.mode-dest) #go-bar { display: none; }
  #go-btn {
    display: block; width: 100%; height: 56px; border: none; border-radius: 18px; cursor: pointer;
    background: var(--apricot); color: var(--basalt-950); font-size: 18px; font-weight: 800; letter-spacing: .005em;
    box-shadow: 0 6px 20px rgba(245,165,54,.28);
  }
  #go-btn:hover { filter: brightness(1.06); }
  #home-btn {
    width: 52px; height: 52px; border-radius: 50%; border: none; flex-shrink: 0; cursor: pointer;
    background: var(--float-bg); color: var(--ui-icon);
    display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 16px rgba(0,0,0,.4);
  }
  #trip-pill { margin-left: auto; }

  /* ================= Route preview ================= */
  .route-canvas { position: absolute; left: 0; top: 0; pointer-events: none; }
  .route-bubble-wrap { width: 0; height: 0; }
  .route-bubble {
    position: absolute; left: 0; bottom: 38px; transform: translateX(-50%);
    background: var(--apricot); color: var(--basalt-950); border-radius: 14px; padding: 6px 11px 7px;
    text-align: center; white-space: nowrap; line-height: 1.1; box-shadow: 0 5px 16px rgba(0,0,0,.5);
    animation: popIn .35s var(--ease) both;
  }
  .route-bubble b { display: block; font-size: 17px; font-weight: 800; }
  .route-bubble span { display: block; font-size: 11px; font-weight: 600; opacity: .78; margin-top: 2px; }
  .route-bubble::after { content: ""; position: absolute; left: 50%; bottom: -5px; width: 10px; height: 10px; background: var(--apricot); transform: translateX(-50%) rotate(45deg); border-radius: 2px; }

  /* ================= "Navigate with" sheet ================= */
  #nav-scrim { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 941; opacity: 0; pointer-events: none; transition: opacity .5s var(--ease-close); }
  #nav-scrim.open { opacity: 1; pointer-events: auto; transition: opacity .3s; }
  #nav-sheet {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 951;
    background: var(--basalt-900); border-radius: var(--sheet-radius) var(--sheet-radius) 0 0;
    padding-bottom: calc(var(--safe-bottom) + 12px);
    transform: translateY(105%); transition: transform .5s var(--ease-close); max-height: 85dvh; overflow-y: auto;
  }
  #nav-sheet.open { transform: none; transition: transform .42s var(--ease-open); }
  #layers-sheet.dragging, #nav-sheet.dragging, #loc-steps.dragging, #menu-drawer.dragging { transition: none !important; }
  #nav-apps { padding-bottom: 4px; }
  .nav-app {
    display: flex; align-items: center; gap: 14px; width: 100%; padding: 11px 18px;
    border: none; background: none; color: var(--ui-text); font-size: 17px; font-weight: 500; text-align: left; cursor: pointer;
  }
  .nav-app:hover { background: rgba(255,255,255,.04); }
  .nav-app-ico { width: 40px; height: 40px; border-radius: 12px; background: var(--basalt-950); color: var(--apricot); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .nav-app small { display: block; font-size: 12.5px; color: var(--fog); font-weight: 400; margin-top: 1px; }
  .nav-app-name { flex: 1; min-width: 0; }
  .nav-last { font-size: 12px; font-weight: 600; color: var(--apricot); }

  /* ================= Menu: the quiet Yandex link ================= */
  .menu-quiet { display: block; width: 100%; padding: 11px 18px; border: none; background: none; text-align: left; cursor: pointer; font-size: 12.5px; color: var(--fog); opacity: .5; }
  .menu-quiet:hover { opacity: .9; }

  /* ================= Which layer is showing ================= */
  body[data-screen="landing"] #sidebar:not(.mode-traffic) { transform: translateY(115%); visibility: hidden; pointer-events: none; transition: transform .5s var(--ease-close), visibility 0s linear .5s; }

  /* ================= Motion ================= */
  @keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(20,21,26,.45); } 70% { box-shadow: 0 0 0 10px rgba(20,21,26,0); } 100% { box-shadow: 0 0 0 0 rgba(20,21,26,0); } }
  @keyframes ringBtn { 0% { box-shadow: 0 0 0 0 rgba(245,165,54,.6), 0 4px 16px rgba(0,0,0,.4); } 70% { box-shadow: 0 0 0 14px rgba(245,165,54,0), 0 4px 16px rgba(0,0,0,.4); } 100% { box-shadow: 0 0 0 0 rgba(245,165,54,0), 0 4px 16px rgba(0,0,0,.4); } }
  @keyframes pulseDot { 0% { box-shadow: 0 0 0 0 rgba(245,165,54,.7); } 70% { box-shadow: 0 0 0 7px rgba(245,165,54,0); } 100% { box-shadow: 0 0 0 0 rgba(245,165,54,0); } }
  @keyframes riseIn   { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
  @keyframes fadeUp   { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
  @keyframes fadeIn   { from { opacity: 0; } to { opacity: 1; } }
  @keyframes paneIn   { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  @keyframes modalIn  { from { opacity: 0; transform: translate(-50%, -46%) scale(.96); } to { opacity: 1; transform: translate(-50%, -50%); } }
  @keyframes popIn    { from { scale: 0; opacity: 0; } 60% { scale: 1.15; } to { scale: 1; opacity: 1; } }
  @keyframes dropIn   { from { opacity: 0; transform: translate(-50%, -14px) scale(.9); } to { opacity: 1; transform: translate(-50%, 0); } }
  @keyframes shimmer  { to { background-position: -200% 0; } }
  @keyframes spin     { to { transform: rotate(360deg); } }
  @keyframes nudgeRight { 0%, 60%, 100% { transform: none; } 30% { transform: translateX(5px); } }
  @keyframes ring     { 0% { box-shadow: inset 0 0 0 0 rgba(245,165,54,.0); } 40% { box-shadow: inset 0 0 0 2px rgba(245,165,54,.65); } 100% { box-shadow: inset 0 0 0 2px rgba(245,165,54,0); } }
  @keyframes pulse    { 0% { box-shadow: 0 0 0 0 rgba(52,199,123,.55); } 70% { box-shadow: 0 0 0 6px rgba(52,199,123,0); } 100% { box-shadow: 0 0 0 0 rgba(52,199,123,0); } }
  @keyframes user-pulse { 0% { transform: translate(-50%, -50%) scale(1); opacity: .8; } 100% { transform: translate(-50%, -50%) scale(3.2); opacity: 0; } }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; animation-delay: 0s !important; transition-duration: .01ms !important; }
  }

  @media (max-width: 768px) { body.admin-on #snack, body.admin-on #parked-toast { left: calc(58px + var(--safe-left)); } }   /* phone/tablet layout only */
  /* a narrow window with a mouse still shows the zoom buttons: keep messages clear of them */

  /* ================= Keyboard + mouse polish (harmless on touch) ================= */
  :focus-visible { outline: 2px solid var(--apricot); outline-offset: 2px; }
  button:focus:not(:focus-visible), [role="switch"]:focus:not(:focus-visible) { outline: none; }
  .dest-title, .rec-name, .search-item-title, .search-item-sub, .leaflet-popup-content, #dest-sub { -webkit-user-select: text; user-select: text; }
  @media (hover: hover) {
    .fab:hover, #locate-btn:hover, .leaflet-control-zoom a:hover { background: var(--basalt-800); }
    .place:hover, .status-pill:hover, #where-btn:hover { background: #2d303b; }
    .rec-card:hover:not(.selected), .search-item:hover, .layer-row:hover { background: rgba(255,255,255,.04); }
    .round-btn:hover { background: #3d404c; }
    #loc-banner-cta:hover, .steps-cta:hover, #nudge-cta:hover { filter: brightness(1.08); }
  }

  /* ================= Laptops and desktops: a floating panel on the left =================
     The panel is the one big thing, so it is sized from the space that is actually free:
       - below the top row (menu button, address header, legend button): --desk-top
       - above the location bar when that is showing (--banner-h)
     The locate button and trip status sit BESIDE the panel, in the map area, so they never cover
     the panel, the top buttons, or each other. */
  @media (min-width: 769px) {
    :root { --desk-top: 72px; }
    body.loc-banner { --banner-h: 66px; }                              /* 52px bar + its 14px margin from the bottom edge */

    #sidebar {
      --desk-free: calc(100dvh - var(--desk-top) - 14px - max(var(--kb, 0px), var(--banner-h)));   /* resolved HERE so it sees the banner */
      right: auto; left: 14px; width: 420px;
      bottom: calc(14px + max(var(--kb, 0px), var(--banner-h)));
      max-height: var(--desk-free);
      border-radius: 24px;
      padding-bottom: 0;
    }
    body.loc-banner #sidebar { padding-bottom: 0; }
    #sidebar.mode-search { bottom: calc(14px + max(var(--kb, 0px), var(--banner-h))); height: min(720px, var(--desk-free)); }
    #sidebar.mode-dest, #sidebar.mode-traffic { max-height: min(70dvh, var(--desk-free)); }
    #sidebar.sheet-collapsed { transform: translateY(calc(100% - 88px)); }

    .sheet-float { left: calc(100% + 12px); right: auto; bottom: 0; width: max-content; justify-content: flex-start; gap: 10px; }
    #sidebar.mode-search .sheet-float { display: flex; }
    /* when the panel shrinks to its small bar, the buttons beside it must not ride down off the screen with it */
    .sheet-float { transition: transform .45s var(--ease-open); }
    #sidebar.sheet-collapsed .sheet-float { transform: translateY(calc(-1 * var(--sb-off, 0px))); transition: transform .5s var(--ease-close); }
    body.admin-on .sheet-float { left: calc(100% + 58px); }     /* make room for the admin toolbar column */

    /* the location bar sits under the panel, same width */
    #loc-banner {
      right: auto; left: 14px; width: 420px; bottom: 14px; height: 52px;
      padding: 7px 12px; border-radius: 16px; transform: translateY(calc(100% + 24px));
    }
    body.loc-banner #loc-banner { transform: none; }

    /* messages go in the map area, clear of the panel and of the top buttons */
    #parked-toast, #snack { left: auto; right: 70px; top: 70px; width: min(380px, calc(100vw - 446px - 84px)); }
    #hint-banner { left: calc(446px + (100% - 446px) / 2); }

    /* map credit bottom-right (the panel would hide it bottom-left); admin toolbar beside the panel */
    .leaflet-control-container .leaflet-bottom.leaflet-left { top: auto; left: auto; right: 8px; bottom: 6px; }
    .leaflet-control-container .leaflet-top.leaflet-left { top: var(--desk-top); left: 446px; }

    #layers-sheet { left: 14px; right: auto; width: 420px; bottom: 14px; border-radius: 24px; }
    #nav-sheet { left: 14px; right: auto; width: 420px; bottom: 14px; border-radius: 24px; }
    #search-page {
      left: 14px; right: auto; width: 420px; top: 14px; height: calc(100dvh - 28px);
      border-radius: 24px; box-shadow: 0 12px 44px rgba(0,0,0,.55); border: 1px solid var(--basalt-line);
      transform: translateX(-26px); opacity: 0; transition: transform .4s var(--ease-close), opacity .4s, visibility 0s .4s;
    }
    #search-page.open { transform: none; opacity: 1; transition: transform .3s var(--ease-open), opacity .3s; }
    .sp-grip { display: none; }
    body.search-open #loc-banner { display: flex; }
    body.loc-banner #search-page { height: calc(100dvh - 28px - var(--banner-h)); }
    .ld-title { margin-top: clamp(32px, 12vh, 110px); }
  }
  /* short windows (small laptops, phones on their side): keep the top row clear */
  @media (min-width: 769px) and (max-height: 560px) {
    :root { --desk-top: 62px; }
    #sidebar.mode-dest, #sidebar.mode-traffic { max-height: var(--desk-free); }
  }
  .search-item-ico { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s-6.5-5.4-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z'/%3E%3Ccircle cx='12' cy='10.5' r='2.3'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-landmark { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%23172a47'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%234d8ff0' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 10 12 4l9 6M5 10v9M9.5 10v9M14.5 10v9M19 10v9M3 20h18'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-street { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2314301f'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%2334c77b' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='5.5' cy='19.5' r='2.2'/%3E%3Ccircle cx='18.5' cy='6.5' r='2.2'/%3E%3Cpath d='M7.7 19.5H14a3.25 3.25 0 0 0 0-6.5H10a3.25 3.25 0 0 1 0-6.5h6.3'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-address { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s-6.5-5.4-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z'/%3E%3Ccircle cx='12' cy='10.5' r='2.3'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-recent { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%23172a47'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%234d8ff0' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='8.5'/%3E%3Cpath d='M12 7.500V12l3 2'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-popular { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s-6.5-5.4-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z'/%3E%3Ccircle cx='12' cy='10.5' r='2.3'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-food { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M7 3v8M4.500 3v4.500a2.500 2.500 0 0 0 5 0V3M7 11v10'/%3E%3Cpath d='M17.500 21V3c-2.500 1.500-3.500 4.500-3.500 8h3.500'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-coffee { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2336232a'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%23d9808a' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M4.500 8.500h11v6a4 4 0 0 1-4 4h-3a4 4 0 0 1-4-4z'/%3E%3Cpath d='M15.500 10h1.800a2.600 2.600 0 0 1 0 5.200h-1.800'/%3E%3Cpath d='M8 3.500v2.200M11.800 3.500v2.200'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-fuel { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%23172a47'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%234d8ff0' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M5 20.500V5.500a2 2 0 0 1 2-2h6.500a2 2 0 0 1 2 2v15'/%3E%3Cpath d='M3.500 20.500h13'/%3E%3Cpath d='M7.500 7.500h5.500'/%3E%3Cpath d='M15.500 10.500h1.200a1.800 1.800 0 0 1 1.800 1.800V17a1.500 1.500 0 0 0 3 0V9.500L18.500 7'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-pharmacy { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2314301f'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%2334c77b' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='4' width='16' height='16' rx='4.500'/%3E%3Cpath d='M12 8v8M8 12h8'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-grocery { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2314301f'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%2334c77b' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3.500 9.500h17l-1.700 9a2 2 0 0 1-2 1.500H7.200a2 2 0 0 1-2-1.500z'/%3E%3Cpath d='m8 9.500 3-5.500M16 9.500 13 4'/%3E%3C/g%3E%3C/svg%3E"); }
  .search-item-ico.kind-atm { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%234a4d5a'/%3E%3Cg transform='translate(4.8 4.8) scale(0.6)' fill='none' stroke='%23eef0f4' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3.500' y='6' width='17' height='12' rx='2.500'/%3E%3Ccircle cx='12' cy='12' r='2.500'/%3E%3Cpath d='M6.500 9.500h.01M17.500 14.500h.01'/%3E%3C/g%3E%3C/svg%3E"); }
  #sidebar.mode-search .place::before { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 21s-6.5-5.4-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.6 12 21 12 21z'/%3E%3Ccircle cx='12' cy='10.5' r='2.3'/%3E%3C/g%3E%3C/svg%3E"); }
  .d-ytraffic::before { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='7.5' y='2.5' width='9' height='19' rx='3.5'/%3E%3Ccircle cx='12' cy='8' r='1.2' fill='%23f5a536'/%3E%3Ccircle cx='12' cy='12' r='1.2' fill='%23f5a536'/%3E%3Ccircle cx='12' cy='16' r='1.2' fill='%23f5a536'/%3E%3C/g%3E%3C/svg%3E"); }
  .d-autopark::before { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2314301f'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%2334c77b' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='4' width='16' height='16' rx='4.5'/%3E%3Cpath d='M10 17V7.5h3a3 3 0 0 1 0 6h-3'/%3E%3C/g%3E%3C/svg%3E"); }
  .nudge-ico.n-location { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%23172a47'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%234d8ff0' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3.5 19.5 20 12 16 4.5 20z'/%3E%3C/g%3E%3C/svg%3E"); }
  .nudge-ico.n-install { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 4v11M7.500 10.500 12 15l4.500-4.500M5 19.500h14'/%3E%3C/g%3E%3C/svg%3E"); }
  .dc-ico { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(4.56 4.56) scale(0.62)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='4' width='16' height='16' rx='4.5'/%3E%3Cpath d='M10 17V7.5h3a3 3 0 0 1 0 6h-3'/%3E%3C/g%3E%3C/svg%3E"); }
  .toast-ico { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%2314301f'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%2334c77b' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='4' y='4' width='16' height='16' rx='4.5'/%3E%3Cpath d='M10 17V7.5h3a3 3 0 0 1 0 6h-3'/%3E%3C/g%3E%3C/svg%3E"); }
  .d-curation::before { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='7.2' fill='%233a2d17'/%3E%3Cg transform='translate(5.04 5.04) scale(0.58)' fill='none' stroke='%23f5a536' stroke-width='2.0' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m4 20 .8-4L16.5 4.3a2.1 2.1 0 0 1 3 3L7.8 19.2z'/%3E%3Cpath d='m14.5 6.3 3 3'/%3E%3C/g%3E%3C/svg%3E"); }
</style>

</head>
<body data-sheet="home" data-screen="landing">

<!-- Shared vector artwork (one car, recoloured per use via currentColor) -->
<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">
  <symbol id="car" viewBox="0 0 64 30">
    <path fill="currentColor" d="M3 23c0-5 2-7 6-8l6-1.5 6.5-7C22.800 5.500 24 5 25.500 5h14c3 0 5 1 6.800 3.300L51 14.500l7 1.800c3 .8 5 2.700 5 6.700v3.500H3z"/>
    <path fill="#14151a" opacity=".78" d="M25.500 8H31v6H20zM34 8h6c1.200 0 2 .4 2.800 1.300L46.500 14H34z"/>
    <circle cx="16" cy="25.500" r="5" fill="#14151a"/><circle cx="16" cy="25.500" r="2" fill="#9498a6"/>
    <circle cx="48" cy="25.500" r="5" fill="#14151a"/><circle cx="48" cy="25.500" r="2" fill="#9498a6"/>
  </symbol>
</svg>

<div id="app">

  <!-- ============ START SCREEN: one line, one search bar, a few quick picks (modelled on Yandex Go's home) ============ -->
  <div id="landing">
    <div class="ld-top">
      <button type="button" class="fab press" id="ld-menu" aria-label="Menu" title="Menu" onclick="openMenu()"><img src="/icon.svg" alt="parkaway" width="46" height="46" /></button>
      <button type="button" id="ld-where" aria-label="Your location" onclick="locateMe()">
        <span class="ld-where-top"><span id="ld-where-label">Parking in</span> &middot; <span id="ld-weather">--°C</span></span>
        <span id="ld-street">Kentron, Yerevan</span>
      </button>
      <button type="button" id="ld-traffic" class="fab traffic-badge press" aria-label="Live traffic" title="Live traffic" onclick="openTraffic()"><span class="traffic-score lvl-Low">–</span></button>
    </div>
    <div class="ld-main">
      <h1 class="ld-title">Looking for parking?</h1>
      <div class="ld-search">
        <button type="button" id="ld-search-btn" class="ld-bar press" onclick="openSearchPage()">
          <span class="ico" style="--icon:var(--i-search)"></span>
          <span class="ld-bar-text">Where to?</span>
        </button>
        <button type="button" id="ld-map-btn" class="ld-map press" aria-label="Choose on the map" title="Choose on the map" onclick="enterMapMode()"><span class="ico" style="--icon:var(--i-map)"></span></button>
      </div>
      <div class="ld-cats" id="ld-cats"></div>
      <div class="ld-list" id="ld-list"></div>
    </div>
  </div>

  <!-- ============ SEARCH: a full-screen page, top-anchored so the keyboard never covers anything ============ -->
  <div id="search-page" role="dialog" aria-label="Search" aria-hidden="true">
    <div class="sp-grip"><div class="handle-bar"></div></div>
    <div class="sp-head">
      <button type="button" id="search-close-btn" aria-label="Back" title="Back (Esc)" onclick="closeSearchPage()"><span class="ico" style="--icon:var(--i-back)"></span></button>
      <div class="search-input-box">
        <input type="text" id="search-input" placeholder="Search a place, address, or “food”" enterkeyhint="search" autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" />
        <button id="search-clear-btn" class="search-clear-btn hidden" aria-label="Clear" onclick="clearSearchInput()">&times;</button>
      </div>
    </div>
    <div id="sp-chips"></div>
    <div id="sp-body">
      <div id="sp-note" class="hidden"></div>
      <div id="search-dropdown" class="search-dropdown hidden"></div>
      <div id="sp-suggest"></div>
    </div>
  </div>

  <!-- ============ NAVIGATE: pick the maps app that takes over ============ -->
  <div id="nav-scrim" onclick="closeNavSheet()"></div>
  <div id="nav-sheet" role="dialog" aria-label="Open in a maps app">
    <div onclick="closeNavSheet()" style="display:flex; justify-content:center; padding:9px 0 8px; cursor:pointer;"><div class="handle-bar"></div></div>
    <div class="layers-title">Navigate with</div>
    <p class="steps-sub" id="nav-sub"></p>
    <div id="nav-apps"></div>
  </div>

  <!-- ============ Bottom sheet. Modes: home / search / dest / traffic (setSheetMode in the script) ============ -->
  <aside id="sidebar" class="mode-home">

    <div class="sheet-float">
      <button type="button" id="home-btn" class="press" aria-label="Back to start" title="Back to start" onclick="showLanding()"><span class="ico" style="--icon:var(--i-back)"></span></button>
      <button type="button" id="locate-btn" class="press" aria-label="Show my location" title="Show my location" onclick="locateMe()"><span class="ico" style="--icon:var(--i-locate)"></span></button>
      <!-- Only visible while a drive is being tracked, so automatic parking detection is never invisible -->
      <button type="button" id="trip-pill" class="chip hidden" onclick="openMenu()"><span class="live-dot"></span><span id="trip-pill-text">Tracking your drive</span></button>
    </div>

    <div id="mobile-sheet-handle"><div class="handle-bar"></div></div>

    <div id="sidebar-scroll">

      <!-- HOME: the one big action -->
      <button type="button" id="where-btn" class="press" onclick="openSearch()">
        <svg class="where-car" aria-hidden="true"><use href="#car"/></svg>
        <span class="where-text">Where to?</span>
        <span class="where-go"><span class="ico" style="--icon:var(--i-arrow)"></span></span>
      </button>

      <!-- Shortcut cards on home, list rows while searching (same element, styled per mode) -->
      <div id="presets"></div>
      <div id="destination-hint" class="sheet-note">Tip: tap anywhere on the map to drop a pin.</div>

      <!-- HOME: one nudge at a time -->
      <div id="nudge-card">
        <div class="nudge-ico" id="nudge-ico"></div>
        <div class="nudge-text"><b id="nudge-title"></b><span id="nudge-body"></span></div>
        <div class="nudge-actions">
          <button type="button" id="nudge-cta" class="press" onclick="nudgeAccept()">Turn on</button>
          <button type="button" id="nudge-dismiss" onclick="nudgeDismiss()">Not now</button>
        </div>
      </div>

      <!-- DESTINATION: where, plus the three best spots -->
      <div id="dest-pane">
        <div id="destination-active">
          <div class="dest-text" onclick="onDestTextTap()">
            <div class="dest-title" id="dest-coords">—</div>
            <div class="dest-sub" id="dest-sub">Finding the best spots…</div>
          </div>
          <button type="button" id="clear-destination" class="round-btn" aria-label="Clear destination" title="Clear destination" onclick="closeDestination()">&times;</button>
        </div>
        <div id="rec-legend" aria-hidden="true">Chance of finding parking</div>
        <div id="rec-list">
          <div id="rec-empty">Set a destination to see the three best-scoring parking spots within 500&nbsp;m — ranked by type, live availability, and distance.</div>
        </div>
      </div>

      <!-- TRAFFIC -->
      <div id="traffic-pane">
        <div class="pane-head">
          <div>
            <div class="dest-title">Live traffic</div>
            <div class="muted">Kentron &middot; updated every 15s</div>
          </div>
          <div style="display:flex; align-items:center;">
            <span class="overall-level" id="overall-level">—</span>
            <button type="button" class="round-btn" aria-label="Close" onclick="closeSearchMode()">&times;</button>
          </div>
        </div>
        <div id="traffic-list"></div>
      </div>

    </div>
    <div id="go-bar" class="hidden">
      <button type="button" id="go-btn" class="press" onclick="startNav()">Let’s go</button>
    </div>
  </aside>

  <div id="map-wrap">

    <button type="button" id="menu-btn" class="fab press" aria-label="Menu" title="Menu" onclick="openMenu()"><img src="/icon.svg" alt="parkaway" width="46" height="46" /></button>

    <button type="button" id="loc-chip" aria-label="Centre on my location" onclick="locateMe()">
      <span class="loc-label"><span id="loc-label-text">Parking in</span> &middot; <span id="weather-display">--°C</span> &rsaquo;</span>
      <span id="loc-street">Kentron, Yerevan</span>
    </button>

    <button type="button" id="layers-btn" class="fab press" aria-label="Map legend" title="Map legend" onclick="openLayers()"><span class="ico" style="--icon:var(--i-layers)"></span></button>

    <button type="button" id="traffic-badge" class="fab traffic-badge press" aria-label="Live traffic" title="Live traffic" onclick="openTraffic()"><span class="traffic-score lvl-Low">–</span></button>

    <div id="map"></div>
    <div id="hint-banner"><span class="dot"></span><span id="hint-text">Tap the map to drop a pin</span></div>

    <!-- Appears when parking was detected automatically; ignoring it is fine, Undo removes the entry -->
    <div id="parked-toast" role="status" aria-live="polite">
      <div class="toast-ico"></div>
      <div class="toast-text">
        <div class="toast-title" id="toast-title">Parked</div>
        <div class="toast-sub">Saved automatically</div>
      </div>
      <button type="button" id="toast-undo" class="press" onclick="undoAutoParked()">Undo</button>
    </div>
    <div id="snack" role="status" aria-live="polite"></div>

    <!-- Full-screen backdrop shown behind any open modal. Without this,
         buttons elsewhere on the page stay clickable while a modal is open,
         letting someone stack up multiple concurrent actions by tapping through. -->
    <div id="modal-backdrop" class="hidden" onclick="handleBackdropClick()"></div>

    <!-- Admin Form Modal Overlay -->
    <div id="admin-modal" class="hidden">
      <h3 id="admin-modal-title">Edit Segment</h3>
      <input type="hidden" id="edit-id" />
      <input type="hidden" id="edit-geom-type" />
      <input type="hidden" id="edit-coords" />

      <div class="admin-field">
        <label for="edit-name">Street / Facility Name</label>
        <input type="text" id="edit-name" placeholder="e.g. Tumanyan Street" />
      </div>

      <div class="admin-field">
        <label for="edit-type">Parking Category</label>
        <select id="edit-type">
          <option value="free">Free Curbside</option>
          <option value="paid">Paid Curbside</option>
          <option value="lot">Structure / Parking Lot</option>
          <option value="unavailable">Unavailable / No Parking</option>
          <option value="unspecified">Unspecified</option>
        </select>
      </div>

      <div class="admin-actions">
        <button class="btn-save" onclick="saveAdminFeature()">Save Segment</button>
        <button class="btn-delete" id="btn-delete" onclick="deleteAdminFeature()">Delete</button>
        <button class="btn-cancel" onclick="closeAdminModal()">Cancel</button>
      </div>
    </div>

    <!-- Admin Login Modal Overlay -->
    <div id="admin-login-modal" class="hidden">
      <h3>Admin Login</h3>
      <div class="admin-field">
        <label for="admin-login-password">Password</label>
        <input type="password" id="admin-login-password" placeholder="Enter admin password"
               onkeydown="if(event.key==='Enter'){event.preventDefault(); submitAdminLogin();}" />
      </div>
      <div id="admin-login-error" style="color:#e74c3c; font-size:12px; min-height:16px; margin-top:-8px;"></div>
      <div class="admin-actions">
        <button class="btn-save" onclick="submitAdminLogin()">Log In</button>
        <button class="btn-cancel" onclick="closeAdminLoginModal()">Cancel</button>
      </div>
    </div>
  </div>

  <!-- LOCATION: a slim bar at the bottom while location is off. Deliberately no dismiss / "Not now". -->
  <div id="loc-banner" role="status" aria-live="polite" aria-hidden="true">
    <span class="loc-banner-ico"><span class="ico" style="--icon:var(--i-locate)"></span></span>
    <div class="loc-banner-text"><b id="loc-banner-title">Turn on location</b><span id="loc-banner-body"></span></div>
    <button type="button" id="loc-banner-cta" class="press" onclick="locBannerAction()">Turn on</button>
  </div>

  <!-- LOCATION: step-by-step for turning it back on in Settings (help, so it can be closed) -->
  <div id="loc-steps-scrim" onclick="closeLocSteps()"></div>
  <div id="loc-steps" role="dialog" aria-label="Turn on location">
    <div onclick="closeLocSteps()" style="display:flex; justify-content:center; padding:9px 0 8px; cursor:pointer;"><div class="handle-bar"></div></div>
    <div class="layers-title" id="loc-steps-title">Turn on location</div>
    <p class="steps-sub" id="loc-steps-note">parkaway needs your location to find parking near you.</p>
    <ol id="loc-steps-list"></ol>
    <button type="button" class="steps-cta press" id="loc-steps-done" onclick="locStepsDone()">I turned it on</button>
  </div>

  {% if yandex_traffic %}
  <!-- Yandex live-traffic map (isolated page in an iframe; see ytraffic_js) -->
  <div id="ytraffic" role="dialog" aria-label="Yandex live traffic">
    <div class="yt-frame"></div>
    <div class="yt-bar">
      <button type="button" class="round-btn" aria-label="Close live traffic" title="Close" onclick="closeYandexTraffic()">&times;</button>
      <div class="yt-title"><b>Live traffic</b><span id="yt-status">Loading…</span></div>
    </div>
    <div id="yt-error">
      <b>Yandex traffic isn’t available right now</b>
      <p>It may be blocked on your network, or the Yandex key isn’t valid for this site.</p>
      <p id="yt-detail" style="font-size:12px; opacity:.75; margin-top:-8px; word-break:break-word;"></p>
      <button type="button" class="steps-cta press" style="margin:0; width:auto; padding:12px 24px;" onclick="closeYandexTraffic()">Back to the map</button>
    </div>
  </div>
  {% endif %}

  <!-- Map legend: the only place the legend lives -->
  <div id="layers-scrim" onclick="closeLayers()"></div>
  <div id="layers-sheet" role="dialog" aria-label="Map legend">
    <div onclick="closeLayers()" style="display:flex; justify-content:center; padding:9px 0 8px; cursor:pointer;"><div class="handle-bar"></div></div>
    <div class="layers-title">Map legend</div>
    <button type="button" id="segments-toggle" class="layer-row seg-toggle press" role="switch" aria-checked="true" onclick="toggleSegments()">
      <span class="layer-ico"><span class="ico" style="--icon:var(--i-layers)"></span></span>
      <span class="layer-name">Show parking segments</span>
      <span class="switch"></span>
    </button>
    <div id="legend">
      <div class="legend-row layer-row"><span class="layer-ico"><span class="swatch" style="background:#e74c3c"></span></span><span class="layer-name">Paid parking (red lines)</span></div>
      <div class="legend-row layer-row"><span class="layer-ico"><span class="swatch" style="background:#2ecc71"></span></span><span class="layer-name">Free curbside lanes</span></div>
      <div class="legend-row layer-row"><span class="layer-ico"><span class="swatch" style="background:#3498db"></span></span><span class="layer-name">Dedicated parking lots</span></div>
      <div class="legend-row layer-row"><span class="layer-ico"><span class="swatch" style="background:#f39c12"></span></span><span class="layer-name">Unavailable / No Parking</span></div>
      <div class="legend-row layer-row"><span class="layer-ico"><span class="swatch" style="background:#7f8c8d"></span></span><span class="layer-name">Unspecified / general</span></div>
    </div>
  </div>

  <!-- Menu: about, how auto-parking works, admin entry -->
  <div id="menu-scrim" onclick="closeMenu()"></div>
  <aside id="menu-drawer" aria-label="Menu">
    <div class="brand">
      <img class="brand-logo" src="/icon.svg" alt="" />
      <h1 class="display">parkaway</h1>
      <p>Live curb &amp; lot availability across central Yerevan, scored against real-time congestion.</p>
    </div>
    <div class="menu-copy">
      <h2>Auto-parking</h2>
      <p>Notices where you park and saves only that spot, never your route. It helps us improve parking estimates.</p>
    </div>
    <button type="button" id="auto-park-toggle" class="layer-row d-row d-autopark" role="switch" aria-checked="true" onclick="toggleAutoPark()">
      <span class="layer-name">Auto-parking<small id="auto-park-state">On</small></span>
      <span class="switch"></span>
    </button>
    <button id="admin-toggle" class="layer-row d-row d-curation" onclick="closeMenu(); toggleAdminMode();">Admin / Curation Mode</button>
    {% if yandex_traffic %}
    <button type="button" id="ytraffic-toggle" class="menu-quiet" aria-checked="false" onclick="toggleYandexTraffic()">Live traffic map · Yandex</button>
    {% endif %}
    <div class="menu-foot"><span class="live-dot"></span><span id="clock">--:--:--</span><span>&middot;</span><span id="data-source-tag">simulated feed</span></div>
  </aside>

</div>

<script>
const CENTER = [{{ center_lat }}, {{ center_lon }}];
const TYPE_LABEL = { free: 'Free', paid: 'Paid', lot: 'Lot', unavailable: 'Unavailable', unspecified: 'Unspecified' };

const PRESETS = [
  { name: 'Northern Ave', lat: 40.1798, lon: 44.5133 },
  { name: 'Opera Theatre', lat: 40.1848, lon: 44.5158 },
  { name: 'Republic Square', lat: 40.1778, lon: 44.5128 },
  { name: 'Cascade', lat: 40.1910, lon: 44.5135 },
  { name: 'Matenadaran', lat: 40.1920, lon: 44.5210 },
  { name: 'Saryan Wine St', lat: 40.1840, lon: 44.5075 }
];

// --------------------------------------------------------------------------
// Google Analytics 4 helper + poster GPS attribution
// --------------------------------------------------------------------------
// Fires a GA4 custom event if analytics is configured; always safe to call
// even when GA4_ENABLED is false (becomes a harmless no-op), so call sites
// never need to check for GA4 themselves.
function gaEvent(name, params) {
  if (!window.GA4_ENABLED || typeof gtag !== 'function') return;
  try {
    gtag('event', name, params || {});
  } catch (e) {
    console.warn('GA4 event failed:', e);
  }
}

// EDIT THESE to match your real poster locations before relying on this for
// attribution. Since all 50 printed posters share one identical QR code (no
// per-poster URL parameter), the only way to tell which poster someone
// scanned is to compare their GPS position - once they grant location
// access, which the app already requests for its normal "show my location"
// feature - against these known poster placement clusters. radius_m is how
// close someone needs to be to count as "at" that location; tune it to
// roughly the area each poster cluster covers.
const POSTER_LOCATIONS = [
  { id: 'poster_site_1', label: 'Poster Site 1 (10 posters) - EDIT LAT/LON', lat: 40.1792, lon: 44.5152, radius_m: 150 },
  { id: 'poster_site_2', label: 'Poster Site 2 (20 posters) - EDIT LAT/LON', lat: 40.1850, lon: 44.5100, radius_m: 150 },
  { id: 'poster_site_3', label: 'Poster Site 3 (20 posters) - EDIT LAT/LON', lat: 40.1750, lon: 44.5200, radius_m: 150 },
];
let posterAttributionSent = false;

function attributePosterScan(lat, lon) {
  if (posterAttributionSent) return; // only fire once per page load
  posterAttributionSent = true;

  let nearest = null;
  let nearestDist = Infinity;
  for (const site of POSTER_LOCATIONS) {
    const d = haversineMeters(lat, lon, site.lat, site.lon);
    if (d < nearestDist) { nearestDist = d; nearest = site; }
  }
  if (!nearest) return;

  const matched = nearestDist <= nearest.radius_m;
  gaEvent('poster_scan_location', {
    poster_location: matched ? nearest.label : 'unmatched',
    poster_location_id: matched ? nearest.id : 'unmatched',
    distance_m: Math.round(nearestDist),
    matched: matched
  });
}

// --------------------------------------------------------------------------

let map, parkingLayer, destMarker;
let recMarkers = [];
let currentDest = null;
let isAdminMode = false;
let searchDebounceTimer = null;
// Holds the raw shape Leaflet-Geoman draws directly on the map while the
// Save/Cancel modal is open for a brand-new (not-yet-saved) segment. Geoman
// adds this layer to the map immediately on drawing, independent of the
// app's real synced data layer (parkingLayer) - if we don't explicitly
// remove it once the modal closes, it lingers on the map forever and looks
// exactly like a saved segment even if it was cancelled or the save failed.
let pendingDrawLayer = null;
// Latest parking segment features (name + centroid), refreshed every time
// loadParkingData() runs. (Previously used by the manual "I Parked Here" flow;
// parking is now detected on the server, so this is kept only as a cache.)
let latestParkingFeatures = [];

// Live GPS state
let userMarker = null;
let userLat = null;
let userLon = null;
let geoWatchId = null;
let hasCenteredOnUser = false;
// Timestamp of the first keystroke in the destination search box since the
// last destination was set/cleared. Used to measure how long someone spent
// searching before picking a destination (GA4 'destination_selected' event).
let searchStartedAt = null;

// Helper function to escape HTML string attributes safely
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {
  initClock();
  initMap();
  renderPresets();
  fetchWeather();
  fetchTraffic();
  initSearchInput();
  initGenericClickTracking();
  setInterval(() => { if (!document.hidden) fetchTraffic(); }, 15000);
  setInterval(() => { if (!document.hidden) fetchWeather(); }, 60000);
});

// Broad, low-effort click tracking: reports every button press by its id
// (or trimmed visible text as a fallback) as a GA4 'ui_click' event, so
// overall interaction/click volume is visible in GA4 without having to wire
// every single button by hand. Specific higher-value actions (destination
// selection, admin login, parking log confirmation, etc.) still fire their
// own more detailed named events elsewhere - this is just the general net.
function initGenericClickTracking() {
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    // Never report the admin password field or anything inside the login
    // modal's input - only the button press itself, never typed content.
    const label = btn.id || (btn.innerText || '').trim().slice(0, 40) || 'unlabeled_button';
    gaEvent('ui_click', { element: label });
  });
}

function initClock() {
  const clockEl = document.getElementById('clock');
  function tick() {
    const d = new Date();
    clockEl.innerText = d.toLocaleTimeString('en-US', { hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

function initMap() {
  map = L.map('map', { zoomControl: false, fadeAnimation: false }).setView(CENTER, 15);
  L.control.zoom({ position: 'bottomright' }).addTo(map);
  // The bottom sheet now covers the map's lower edge, so the attribution is
  // moved to the top-left (see .leaflet-bottom.leaflet-left in the CSS).
  map.attributionControl.setPosition('bottomleft');

  // Standard OpenStreetMap raster tiles: no API key, no usage-tracking
  // account needed. Previously used CARTO's "Voyager" style
  // (basemaps.cartocdn.com), which started requiring an API key and
  // watermarking unauthenticated tiles with "API KEY REQUIRED" as of late
  // August 2026 - switching provider entirely avoids relying on any single
  // company's free-tier terms not changing again. Visual style is the
  // standard OSM look (a bit more colorful/detailed than Voyager's muted
  // style) rather than a functional change.
  createBaseTileLayer().addTo(map);

  loadParkingData();

  map.on('click', (e) => {
    if (isAdminMode) return;
    setDestination(e.latlng.lat, e.latlng.lng, 'Dropped pin', 'map_click');
  });
}

// --------------------------------------------------------------------------
// Live GPS Location (requests permission once, then tracks continuously
// while the app is open; independent of the destination pin so searching
// for / clicking a destination never moves or clears the user's live dot)
// --------------------------------------------------------------------------

function updateUserLocation(pos) {
  recordFix(pos); // every GPS fix also feeds automatic parking detection
  updateWhere(pos.coords.latitude, pos.coords.longitude); // "Your location" chip
  userLat = pos.coords.latitude;
  userLon = pos.coords.longitude;

  if (userMarker) {
    userMarker.setLatLng([userLat, userLon]);
  } else {
    const userIcon = L.divIcon({
      className: 'user-marker-wrap',
      html: '<div class="user-location-pulse"></div><div class="user-location-marker"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8]
    });
    userMarker = L.marker([userLat, userLon], { icon: userIcon, zIndexOffset: 400 }).addTo(map);
    userMarker.bindPopup('<div style="font-family:\'Inter\',sans-serif; color:#14151a;"><strong>Your location</strong></div>');
  }

  // Only auto-center the map on the very first GPS fix, so the user can
  // freely pan/search afterwards without the map jumping back to them.
  if (!hasCenteredOnUser) {
    hasCenteredOnUser = true;
    map.setView([userLat, userLon], 16);
  }
}

// --------------------------------------------------------------------------
// Address Search Bar & Autocomplete Logic
// --------------------------------------------------------------------------

function initSearchInput() {
  const searchInput = document.getElementById('search-input');
  const searchClearBtn = document.getElementById('search-clear-btn');
  const searchDropdown = document.getElementById('search-dropdown');

  searchInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (val.length > 0) {
      if (searchStartedAt === null) searchStartedAt = Date.now();
      searchClearBtn.classList.remove('hidden');
    } else {
      searchClearBtn.classList.add('hidden');
      searchDropdown.classList.add('hidden');
      return;
    }

    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
      fetchSearchResults(val);
    }, 220);
  });

  searchInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      const firstItem = searchDropdown.querySelector('.search-item');
      if (firstItem) {
        firstItem.click();
      } else if (searchInput.value.trim().length >= 2) {
        clearTimeout(searchDebounceTimer);
        fetchSearchResults(searchInput.value.trim());
      }
    } else if (e.key === 'Escape') {
      searchDropdown.classList.add('hidden');
    }
  });

}

function clearSearchInput() {
  const searchInput = document.getElementById('search-input');
  const searchClearBtn = document.getElementById('search-clear-btn');
  const searchDropdown = document.getElementById('search-dropdown');
  searchInput.value = '';
  searchClearBtn.classList.add('hidden');
  searchDropdown.classList.add('hidden');
  searchInput.focus();
  searchStartedAt = null;
}

async function fetchSearchResults(query) {
  try {
    let searchUrl = `/api/search?q=${encodeURIComponent(query)}`;
    if (userLat != null && userLon != null) searchUrl += `&lat=${userLat}&lon=${userLon}`;
    const resp = await fetch(searchUrl);
    const results = await resp.json();
    // A slow response must not resurrect results for a query that is no longer in the box.
    if (document.getElementById('search-input').value.trim() !== query) return;
    renderSearchDropdown(results);
  } catch (err) {
    console.error('Search error:', err);
  }
}

function renderSearchDropdown(results) {
  const searchDropdown = document.getElementById('search-dropdown');
  searchDropdown.innerHTML = '';

  if (!results || results.length === 0) {
    searchDropdown.innerHTML = '<div class="search-no-results">No matching locations found</div>';
    searchDropdown.classList.remove('hidden');
    return;
  }

  results.forEach(item => {
    const div = document.createElement('div');
    div.className = 'search-item';
    div.innerHTML = `
      <div class="search-item-ico kind-${escapeHtml(item.kind || 'place')}"></div>
      <div class="search-item-text">
        <div class="search-item-title">${escapeHtml(item.title)}</div>
        <div class="search-item-sub">${escapeHtml(item.subtitle)}</div>
      </div>
      <div class="search-item-dist">${formatDistance(item.distance_m)}</div>
    `;
    div.onclick = () => {
      selectSearchLocation(item);
    };
    searchDropdown.appendChild(div);
  });

  searchDropdown.classList.remove('hidden');
}

function selectSearchLocation(item) {
  const searchInput = document.getElementById('search-input');
  const searchDropdown = document.getElementById('search-dropdown');
  searchInput.value = item.title;
  searchDropdown.classList.add('hidden');

  map.setView([item.lat, item.lon], 16);
  setDestination(item.lat, item.lon, item.title, 'search');
}

// --------------------------------------------------------------------------
// Core Parking & Recommender Engine Interactions
// --------------------------------------------------------------------------

function loadParkingData(retryCount) {
  retryCount = retryCount || 0;
  if (parkingLayer) map.removeLayer(parkingLayer);

  fetch('/api/parking', { cache: 'no-store' })
    .then(r => {
      if (!r.ok) throw new Error(`/api/parking returned ${r.status}`);
      return r.json();
    })
    .then(data => {
      const features = [];
      const rawData = Array.isArray(data) ? data : (data.features || []);

      rawData.forEach(item => {
        let coords = item.coordinates || (item.geometry && item.geometry.coordinates);
        let type = item.geometry_type || (item.geometry && item.geometry.type) || 'LineString';

        if (!coords || coords.length === 0) return;

        // 1. Fix Flat 1D Arrays (if backend sends [lat, lon, lat, lon])
        if (typeof coords[0] === 'number') {
          const paired = [];
          for (let i = 0; i < coords.length; i += 2) {
            paired.push([coords[i], coords[i+1]]);
          }
          coords = paired;
        }

        // 2. Fix Lat/Lon Inversion (GeoJSON strictly requires [Lon, Lat])
        // Yerevan is roughly Lat 40.1, Lon 44.5. 
        const normalizePoint = (pt) => {
          // If the first coordinate is ~40, it's Latitude. Swap to [Lon, Lat].
          if (pt[0] > 39 && pt[0] < 42 && pt[1] > 43 && pt[1] < 46) {
            return [pt[1], pt[0]];
          }
          return pt;
        };

        if (type === 'LineString') {
          coords = coords.map(normalizePoint);
        } else if (type === 'Polygon' || type === 'MultiLineString') {
          coords = coords.map(ring => ring.map(normalizePoint));
        }

        features.push({
          type: "Feature",
          properties: item.properties || item,
          geometry: {
            type: type,
            coordinates: coords
          }
        });
      });

      latestParkingFeatures = features;

      // Drawn on ONE canvas (see getParkingRenderer / parkingStyle): far lighter than SVG on phones.
      const parkingGeo = L.geoJSON({ type: "FeatureCollection", features: features }, {
        renderer: getParkingRenderer(),
        style: parkingStyle,
        onEachFeature: (feature, layer) => {
          const props = feature.properties;
          layer.bindPopup(`
            <div>
              <strong>${escapeHtml(props.name || 'Segment')}</strong>
              <div class="pk-pop-row"><span>${TYPE_LABEL[props.parking_type] || props.parking_type || 'Unspecified'}</span> &middot; <b>${props.availability_pct || '--'}%</b> <span>free</span></div>
              <div class="pk-pop-row"><span>Traffic</span> <b>${props.traffic_level || '--'}</b></div>
              ${isAdminMode ? `<div class="pk-pop-row"><span>${props.centroid_lat != null ? props.centroid_lat.toFixed(5) : '--'}, ${props.centroid_lon != null ? props.centroid_lon.toFixed(5) : '--'}</span></div>` : ''}
            </div>
          `);

          if (isAdminMode) {
            layer.on('click', (e) => {
              L.DomEvent.stopPropagation(e);
              openAdminModal(feature);
            });
          }
        }
      });
      parkingLayer = assembleParkingLayer(features, parkingGeo);
      applyParkingVisibility();
    })
    .catch(err => {
      console.error("Error loading parking data:", err);
      // The very first load on a cold-starting Render instance (or a brief
      // network hiccup) can fail outright, and previously there was no
      // recovery from that - the map would just silently stay empty of
      // parking segments until something else happened to reload the page.
      // Retry a few times with increasing delay before giving up.
      const MAX_RETRIES = 4;
      if (retryCount < MAX_RETRIES) {
        const delayMs = 1500 * Math.pow(1.6, retryCount); // ~1.5s, 2.4s, 3.8s, 6.1s
        console.warn(`Retrying parking data load (attempt ${retryCount + 1}/${MAX_RETRIES}) in ${Math.round(delayMs)}ms...`);
        setTimeout(() => loadParkingData(retryCount + 1), delayMs);
      } else {
        console.error("Giving up on loading parking data after several retries.");
      }
    });
}

function setDestination(lat, lon, label, method) {
  currentDest = { lat, lon, label };

  if (destMarker) map.removeLayer(destMarker);

  const destIcon = L.divIcon({
    className: 'dest-callout-wrap',
    html: destCalloutHtml(label),
    iconSize: [0, 0],
    iconAnchor: [0, 0]
  });

  destMarker = L.marker([lat, lon], { icon: destIcon, zIndexOffset: 1000, interactive: false, keyboard: false }).addTo(map);

  document.getElementById('destination-active').style.display = 'flex';
  document.getElementById('dest-coords').innerText = label;

  const eventParams = { method: method || 'unknown', destination_label: label };
  if (method === 'search' && searchStartedAt !== null) {
    eventParams.search_duration_ms = Date.now() - searchStartedAt;
  }
  gaEvent('destination_selected', eventParams);
  searchStartedAt = null; // reset for the next search

  onDestinationSet(lat, lon, label, method);
  fetchRecommendations(lat, lon);
}

function clearDestination() {
  currentDest = null;
  if (destMarker) map.removeLayer(destMarker);
  recMarkers.forEach(m => map.removeLayer(m));
  recMarkers = [];

  document.getElementById('destination-active').style.display = 'none';
  document.getElementById('rec-list').innerHTML = `
    <div id="rec-empty">Set a destination to see the three best-scoring parking spots within 500&nbsp;m — ranked by type, live availability, and distance.</div>
  `;
  onDestinationCleared();
}

function renderRecommendations(recs) {
  updateDestSummary(recs);
  recMarkers.forEach(m => map.removeLayer(m));
  recMarkers = [];

  const container = document.getElementById('rec-list');
  container.innerHTML = '';

  if (!recs || recs.length === 0) {
    container.innerHTML = '<div id="rec-empty">No parking options available near this destination.</div>';
    return;
  }

  recs.forEach((r, idx) => {
    const rank = idx + 1;
    const markerIcon = L.divIcon({
      className: 'rec-marker-wrap',
      html: `<div class="rec-marker"><span>${rank}</span></div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 26]
    });

    const m = L.marker([r.location.lat, r.location.lon], { icon: markerIcon, zIndexOffset: 200 }).addTo(map);
    m.options.title = `#${rank} ${r.name}`;
    recMarkers.push(m);

    const card = document.createElement('div');
    card.className = 'rec-card';
    card.setAttribute('role', 'button');
    card.tabIndex = 0;
    card.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chooseRec(idx); } });

    const pillClass = `pill-${r.parking_type}`;

    card.innerHTML = `
      <div class="rec-rank">${rank}</div>
      <div class="rec-body">
        <div class="rec-name">${escapeHtml(r.name)}</div>
        <div class="rec-meta">
          <span class="pill ${pillClass}">${TYPE_LABEL[r.parking_type] || r.parking_type}</span>
          <span>${r.distance_m}m</span>
          <span>&bull;</span>
          <span>~${r.walk_time_min}m walk</span>
        </div>
      </div>
      <div class="gauge" style="background: conic-gradient(var(--apricot) ${r.final_score}%, var(--basalt-700) 0)">
        <div class="gauge-inner">${r.final_score}</div>
      </div>
    `;
    container.appendChild(card);
  });
  onRecommendationsRendered(recs);
}

function fetchWeather() {
  fetch('/api/weather')
    .then(r => r.json())
    .then(w => {
      document.getElementById('weather-display').innerText = w.summary || `${w.temp_c}°C, ${w.condition}`;
    });
}

function fetchTraffic() {
  fetch('/api/traffic')
    .then(r => r.json())
    .then(data => {
      document.getElementById('overall-level').innerText = data.overall_level;
      updateTrafficBadge(data);
      updateDataSourceTag(data);
      const container = document.getElementById('traffic-list');
      container.innerHTML = '';
      (data.streets || []).slice(0, 8).forEach(s => {
        const row = document.createElement('div');
        row.className = 'traffic-card';
        row.innerHTML = `
          <span class="traffic-name">${escapeHtml(s.name)}</span>
          <span class="traffic-badge badge-${s.traffic_level}">${s.traffic_level}</span>
        `;
        container.appendChild(row);
      });
    });
}

function toggleMobileSheet() {
  const sidebar = document.getElementById('sidebar');
  sidebar.classList.toggle('sheet-collapsed');
}

function collapseMobileSheet() {
  document.getElementById('sidebar').classList.add('sheet-collapsed');
}

// --------------------------------------------------------------------------
// Swipe-to-dismiss for the mobile bottom sheet. The handle bar previously
// only responded to a tap, which many people don't realize is tappable at
// all (a bar with no visible button doesn't read as "press me"). Real
// drag-following, snapping to open/closed on release, matches how bottom
// sheets behave in every native app, so it's discoverable without
// instructions.
// --------------------------------------------------------------------------
// --------------------------------------------------------------------------
// Admin Curation & ML Feedback Logic
// --------------------------------------------------------------------------
let adminSessionPollTimer = null;

function toggleAdminMode() {
  if (isAdminMode) {
    // Exiting: also invalidate the server-side session so a lost/borrowed
    // phone doesn't leave a standing admin session behind.
    fetch('/api/admin/logout', { method: 'POST', cache: 'no-store' }).catch(() => {});
    setAdminModeUI(false);
    loadParkingData();
    return;
  }

  // Entering: check whether we already have a valid session (e.g. logged in
  // earlier this browser session, and it hasn't timed out yet) before
  // bothering to prompt for a password.
  fetch('/api/admin/status', { cache: 'no-store' })
    .then(r => r.json())
    .then(({ is_admin }) => {
      if (is_admin) {
        setAdminModeUI(true);
        loadParkingData();
      } else {
        openAdminLoginModal();
      }
    })
    .catch(() => openAdminLoginModal());
}

function setAdminModeUI(enabled) {
  isAdminMode = enabled;
  const btn = document.getElementById('admin-toggle');
  if (enabled) {
    btn.classList.add('active');
    btn.innerText = 'Exit Curation Mode';
    if (map.pm) {
      map.pm.addControls({ position: 'topleft', drawCircle: false, drawMarker: false });
      map.on('pm:create', onGeomanCreate);
    }
    startAdminSessionPolling();
  } else {
    btn.classList.remove('active');
    btn.innerText = 'Admin / Curation Mode';
    if (map.pm) {
      map.pm.removeControls();
      map.off('pm:create', onGeomanCreate);
    }
    closeAdminModal();
    stopAdminSessionPolling();
  }
}

// Proactively checks whether the admin session has timed out, instead of
// only discovering it the next time a save/delete happens to fail. Once the
// session's time limit (ADMIN_SESSION_HOURS on the server, default 2h) is
// up, this automatically exits Curation Mode on this device and explains
// why, rather than leaving stale admin controls sitting on screen.
function startAdminSessionPolling() {
  stopAdminSessionPolling();
  adminSessionPollTimer = setInterval(() => {
    fetch('/api/admin/status', { cache: 'no-store' })
      .then(r => r.json())
      .then(({ is_admin }) => {
        if (!is_admin && isAdminMode) {
          setAdminModeUI(false);
          alert('Your admin session has timed out. Please log in again to keep editing.');
        }
      })
      .catch(() => {}); // a transient network hiccup shouldn't force a logout
  }, 60000); // check once a minute
}

function stopAdminSessionPolling() {
  if (adminSessionPollTimer) {
    clearInterval(adminSessionPollTimer);
    adminSessionPollTimer = null;
  }
}

function openAdminLoginModal() {
  const pwField = document.getElementById('admin-login-password');
  const errField = document.getElementById('admin-login-error');
  if (pwField) pwField.value = '';
  if (errField) errField.textContent = '';
  document.getElementById('admin-login-modal').classList.remove('hidden');
  showModalBackdrop();
  if (pwField) pwField.focus();
}

function closeAdminLoginModal() {
  document.getElementById('admin-login-modal').classList.add('hidden');
  hideModalBackdrop();
}

function submitAdminLogin() {
  const pwField = document.getElementById('admin-login-password');
  const errField = document.getElementById('admin-login-error');
  const password = pwField ? pwField.value : '';

  fetch('/api/admin/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
    cache: 'no-store'
  })
    .then(r => r.json().then(body => ({ ok: r.ok, body })))
    .then(({ ok, body }) => {
      if (!ok) {
        gaEvent('admin_login_failed', {});
        if (errField) errField.textContent = body.error || 'Login failed.';
        return;
      }
      gaEvent('admin_login_success', {});
      closeAdminLoginModal();
      setAdminModeUI(true);
      loadParkingData();
    })
    .catch(() => {
      if (errField) errField.textContent = 'Network error. Please try again.';
    });
}

function onGeomanCreate(e) {
  const layer = e.layer;
  pendingDrawLayer = layer;
  const geojson = layer.toGeoJSON();
  openAdminModal({
    properties: { id: 'seg_' + Date.now(), name: '', parking_type: 'free' },
    geometry: geojson.geometry
  });
}

// --------------------------------------------------------------------------
// Automatic parking detection (replaces the manual "I Parked Here" button)
//
// The device only does the sensing: it forwards its latest GPS fix to
// /api/trip/ping every few seconds while a drive is in progress. All of the
// decisions - "was that a drive?", "has the car stopped long enough?", "is it
// near the destination?" - are made by the backend (see _advance_trip in
// app.py), which writes the parking record itself. Nothing is asked of the
// user; a toast with Undo appears afterwards in case it guessed wrong.
//
// What a web app CAN'T see: CarPlay / Bluetooth connections and background
// location (browsers suspend the page when the screen locks). To cope with
// that the backend also infers "parked" when pings simply stop near the
// destination, and the screen is kept awake (Wake Lock) while driving. The
// charger being unplugged is reported where the browser exposes it
// (Battery Status API, Chrome on Android).
// --------------------------------------------------------------------------
const AUTO_PARK_PREF_KEY = 'parkaway.autoParking';
const PING_INTERVAL_MS = 5000;
const VEHICLE_SPEED_MS = 4;                    // ~14 km/h; walking is ~1.4 m/s. Keep in sync with TRIP_CFG on the server.
const TRACK_AFTER_DRIVE_MS = 10 * 60 * 1000;   // keep reporting this long after the last moment of vehicle-speed motion
const FIX_STALE_MS = 8000;                     // watchPosition goes quiet when you stand still: treat an old fix as speed 0
const TOAST_MS = 14000;

let autoParkEnabled = true;
try { autoParkEnabled = localStorage.getItem(AUTO_PARK_PREF_KEY) !== 'off'; } catch (e) {}

let tripId = null;
let lastFix = null;            // { lat, lon, accuracy, speed (m/s or null), ts }
let lastVehicleAt = 0;         // last time the fix showed vehicle-speed motion
let needDriveToResume = false; // after a parking event, stay quiet until the next drive begins
let tripPingInFlight = false;
let tripBackoffUntil = 0;
let batteryInfo = null;
let wakeLockSentinel = null;
let toastTimer = null;
let lastParked = null;         // { log_id, undo_token } for the Undo button

function haversineMeters(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function newTripId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return 't' + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
}

// Called from updateUserLocation() for every GPS fix.
function recordFix(pos) {
  const c = pos.coords;
  const now = Date.now();
  let speed = (typeof c.speed === 'number' && isFinite(c.speed) && c.speed >= 0) ? c.speed : null;
  if (speed === null && lastFix) {
    // Some browsers don't report speed: derive it from the last two fixes.
    const dt = (now - lastFix.ts) / 1000;
    if (dt >= 1 && dt <= 30) speed = haversineMeters(lastFix.lat, lastFix.lon, c.latitude, c.longitude) / dt;
  }
  lastFix = { lat: c.latitude, lon: c.longitude, accuracy: c.accuracy, speed: speed, ts: now };
  if (speed !== null && speed >= VEHICLE_SPEED_MS) {
    lastVehicleAt = now;
    needDriveToResume = false;
    acquireWakeLock();
  }
}

function shouldTrack() {
  if (!autoParkEnabled || !lastFix) return false;
  const drivingRecently = Date.now() - lastVehicleAt < TRACK_AFTER_DRIVE_MS;
  return drivingRecently || (!!currentDest && !needDriveToResume);
}

async function tripTick() {
  if (tripPingInFlight || Date.now() < tripBackoffUntil || !shouldTrack()) return;
  if (!tripId) tripId = newTripId();

  const age = Date.now() - lastFix.ts;
  const body = {
    trip_id: tripId,
    lat: lastFix.lat,
    lon: lastFix.lon,
    accuracy: lastFix.accuracy,
    speed: age > FIX_STALE_MS ? 0 : lastFix.speed,
    charging: batteryInfo ? !!batteryInfo.charging : null,
    dest_lat: currentDest ? currentDest.lat : null,
    dest_lon: currentDest ? currentDest.lon : null
  };

  tripPingInFlight = true;
  try {
    const r = await fetch('/api/trip/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store'
    });
    if (r.status === 429) { tripBackoffUntil = Date.now() + 30000; return; }
    if (!r.ok) return;
    handleTripResponse(await r.json());
  } catch (err) {
    // Offline / server asleep: just try again on the next tick.
  } finally {
    tripPingInFlight = false;
  }
}

function handleTripResponse(data) {
  setTripPill(data.state);
  if (data.keep_tracking === false) tripBackoffUntil = Date.now() + 5 * 60 * 1000;
  if (data.parked) {
    onAutoParked(data.parked);
    resetTrip();
  } else if (data.state === 'parked' || data.state === 'discarded') {
    resetTrip();
  }
}

function resetTrip() {
  tripId = null;
  lastVehicleAt = 0;
  needDriveToResume = true;
  releaseWakeLock();
  setTripPill(null);
}

function setTripPill(state) {
  const pill = document.getElementById('trip-pill');
  const txt = document.getElementById('trip-pill-text');
  if (!pill || !txt) return;
  if (state === 'driving') { txt.textContent = 'Tracking your drive'; pill.classList.remove('hidden'); }
  else if (state === 'stopped') { txt.textContent = 'Checking if you parked…'; pill.classList.remove('hidden'); }
  else pill.classList.add('hidden');
}

function onAutoParked(info) {
  lastParked = { log_id: info.log_id, undo_token: info.undo_token };
  gaEvent('auto_parked', { source: info.source || 'unknown', matched: info.segment_name ? 1 : 0 });
  document.getElementById('toast-title').textContent =
    info.segment_name ? `Parked near ${info.segment_name}` : 'Parking spot saved';
  const toast = document.getElementById('parked-toast');
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), TOAST_MS);
}

async function undoAutoParked() {
  const toast = document.getElementById('parked-toast');
  toast.classList.remove('show');
  clearTimeout(toastTimer);
  if (!lastParked) return;
  const target = lastParked;
  lastParked = null;
  gaEvent('auto_parked_undo', {});
  try {
    await fetch('/api/trip/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(target),
      cache: 'no-store'
    });
  } catch (err) {
    console.warn('Undo request failed:', err);
  }
}

// Keep the screen on while driving so the browser keeps delivering GPS fixes.
async function acquireWakeLock() {
  if (!autoParkEnabled || wakeLockSentinel || !('wakeLock' in navigator)) return;
  try {
    wakeLockSentinel = await navigator.wakeLock.request('screen');
    wakeLockSentinel.addEventListener('release', () => { wakeLockSentinel = null; });
  } catch (err) { /* denied or unsupported: detection still works, just less reliably */ }
}

function releaseWakeLock() {
  if (wakeLockSentinel) { wakeLockSentinel.release().catch(() => {}); wakeLockSentinel = null; }
}

function renderAutoParkState() {
  document.getElementById('auto-park-toggle').setAttribute('aria-checked', String(autoParkEnabled));
  document.getElementById('auto-park-state').textContent = autoParkEnabled ? 'On' : 'Off';
}

function toggleAutoPark() {
  autoParkEnabled = !autoParkEnabled;
  try { localStorage.setItem(AUTO_PARK_PREF_KEY, autoParkEnabled ? 'on' : 'off'); } catch (e) {}
  renderAutoParkState();
  gaEvent('auto_parking_toggle', { enabled: autoParkEnabled ? 1 : 0 });
  if (!autoParkEnabled) { tripId = null; releaseWakeLock(); setTripPill(null); }
}

function initAutoParking() {
  renderAutoParkState();
  if (navigator.getBattery) {
    navigator.getBattery().then(b => { batteryInfo = b; }).catch(() => {});
  }
  setInterval(tripTick, PING_INTERVAL_MS);
  // Coming back to the app after it was in the background: report straight away so
  // the backend can settle a drive that ended while the page was suspended.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    tripTick();
    if (Date.now() - lastVehicleAt < TRACK_AFTER_DRIVE_MS) acquireWakeLock();
  });
}
document.addEventListener('DOMContentLoaded', initAutoParking);

// --------------------------------------------------------------------------
// Shared modal backdrop: shown behind whichever modal is open, so buttons
// elsewhere on the page can't be tapped through to it (this was the actual
// cause of the "I Parked Here" bug where repeated presses + Cancel stacked
// up multiple concurrent GPS lookups - the confirm modal never blocked
// clicks to the button underneath it).
// --------------------------------------------------------------------------
function showModalBackdrop() {
  document.getElementById('modal-backdrop').classList.remove('hidden');
}

function hideModalBackdrop() {
  document.getElementById('modal-backdrop').classList.add('hidden');
}

function handleBackdropClick() {
  if (!document.getElementById('admin-modal').classList.contains('hidden')) { closeAdminModal(); return; }
  if (!document.getElementById('admin-login-modal').classList.contains('hidden')) { closeAdminLoginModal(); return; }
}

function openAdminModal(feature) {
  const props = feature.properties || feature;
  const geom = feature.geometry || {};
  
  document.getElementById('edit-id').value = props.id || '';
  document.getElementById('edit-name').value = props.name || '';
  document.getElementById('edit-type').value = props.parking_type || 'free';
  document.getElementById('edit-geom-type').value = geom.type || 'LineString';
  document.getElementById('edit-coords').value = geom.coordinates ? JSON.stringify(geom.coordinates) : '';

  document.getElementById('admin-modal').classList.remove('hidden');
  showModalBackdrop();
}

function closeAdminModal() {
  document.getElementById('admin-modal').classList.add('hidden');
  hideModalBackdrop();
  // Remove Geoman's raw drawn layer if one is pending. On a successful save,
  // loadParkingData() (called right after this) redraws the authoritative
  // version from the server, so this temp layer must not be left behind as
  // a visual duplicate that was never actually persisted.
  if (pendingDrawLayer) {
    map.removeLayer(pendingDrawLayer);
    pendingDrawLayer = null;
  }
}

// Shared handler for admin API responses: if the session expired mid-use
// (401), drop back to logged-out state and re-prompt for the password
// instead of just showing a raw error the person can't act on.
function handleAdminAuthFailure(status, body) {
  if (status === 401) {
    setAdminModeUI(false);
    alert('Your admin session has expired. Please log in again.');
    openAdminLoginModal();
    return true;
  }
  return false;
}

function saveAdminFeature() {
  const id = document.getElementById('edit-id').value || 'seg_' + Date.now();
  const name = document.getElementById('edit-name').value || 'New Segment';
  const parkingType = document.getElementById('edit-type').value;
  const geomType = document.getElementById('edit-geom-type').value || 'LineString';
  const coordsRaw = document.getElementById('edit-coords').value;

  let coords;
  try {
    coords = coordsRaw ? JSON.parse(coordsRaw) : [[44.5122, 40.1808], [44.5133, 40.1795]];
  } catch (e) {
    coords = [[44.5122, 40.1808], [44.5133, 40.1795]];
  }

  const payload = {
    id: id,
    name: name,
    parking_type: parkingType,
    geometry_type: geomType,
    coordinates: coords
  };

  fetch('/api/admin/feature', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    cache: 'no-store'
  })
  .then(r => r.json().then(body => ({ status: r.status, ok: r.ok, body })))
  .then(({ status, ok, body }) => {
    if (!ok) {
      if (handleAdminAuthFailure(status, body)) return;
      alert(body.error || 'Could not save this segment.');
      return;
    }
    closeAdminModal();
    loadParkingData();
  })
  .catch(err => console.error('Error saving feature:', err));
}

function deleteAdminFeature() {
  const id = document.getElementById('edit-id').value;
  if (!id) {
    closeAdminModal();
    return;
  }
  
  fetch(`/api/admin/feature/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    cache: 'no-store'
  })
  .then(r => r.json().then(body => ({ status: r.status, ok: r.ok, body })))
  .then(({ status, ok, body }) => {
    if (!ok) {
      if (handleAdminAuthFailure(status, body)) return;
      alert(body.error || 'Could not delete this segment.');
      return;
    }
    closeAdminModal();
    loadParkingData();
  })
  .catch(err => {
    console.error('Error deleting feature:', err);
    closeAdminModal();
  });
}

// --------------------------------------------------------------------------
// Location. The app is much less useful without it, so this module:
//   1. asks in a way that works on iPhone (the request is made synchronously inside the tap)
//   2. never fails silently: every outcome becomes a clear message + the right next step
//   3. asks ONCE with a proper explanation, then stays out of the way; if location is off it
//      keeps a message on the bottom of the screen that can't be dismissed (no "Not now")
//   4. notices on its own when the user fixes it in Settings, and when the app resumes
//
// What was wrong before (the "arrow button does nothing" bug):
//   - the only error handler was console.warn: denied / timed out / unavailable all looked the same
//   - the first request asked for high-accuracy GPS with maximumAge 0 and a 10 s timeout, which an
//     iPhone often can't satisfy indoors, so it timed out silently
//   - the button first waited on the Permissions API (which can hang in an iOS home-screen app) and
//     only THEN asked for the position, outside the tap, where iOS may refuse to show the prompt
//   - nothing re-checked after the user changed the setting, and a watch that iOS suspended in the
//     background was never restarted
// --------------------------------------------------------------------------
const LOC_EVER_KEY  = 'parkaway.locGranted';     // a position has worked on this device before
const LOC_GOOD_M = 800;                           // accurate enough to trust (demo pin, centring)
const LOC_IMPRECISE_M = 1500;                     // iOS "Precise Location: off" gives ~5-10 km
const LOC_RETRY_MS = [1500, 3000, 5000, 8000];    // pauses between retries of a request that failed for a transient reason

let locPerm = 'unknown';        // what the browser CLAIMS (informational only, never trusted to decide anything)
let locProblem = null;          // null | denied | stuck | timeout | unavailable | imprecise | unsupported
let locBusy = false;
let locBusySource = null;
let locBusySince = 0;
let locReq = 0;                 // token: a newer request / a fix cancels older retries
let locRetryTimer = null;
let locFixAt = 0;
let locFirstAccuracy = null;
let locAccuracy = null;         // accuracy (m) of the latest fix
let locWatchId = null;
let locAttributed = false;
let locRefined = false;
let probeTimer = null;
let lastBannerKey = '';
let locStepsKind = null;        // which message the steps sheet is showing (denied / imprecise / reprompt)
let locPermAtLaunch = 'unknown';// what the browser said BEFORE this launch's request was answered ('prompt' = it will ask)
let locWarnAt = 0;
const LOC_TIP_KEY = 'parkaway.repromptTip';   // the one-time "iPhone keeps asking" tip has been shown

const locSupported = () => 'geolocation' in navigator;
const isIosDevice = () => /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const isAndroidDevice = () => /android/i.test(navigator.userAgent);

// ---- permission state (never trusted to answer: it can hang) -------------------
function queryLocPermission(ms) {
  return new Promise(resolve => {
    if (!(navigator.permissions && navigator.permissions.query)) return resolve('unknown');
    let done = false;
    const t = setTimeout(() => { if (!done) { done = true; resolve('unknown'); } }, ms || 1500);
    navigator.permissions.query({ name: 'geolocation' }).then(p => {
      p.onchange = () => refreshLocationState();       // changed in Settings / the prompt answered
      if (!done) { done = true; clearTimeout(t); resolve(p.state); }
    }).catch(() => { if (!done) { done = true; clearTimeout(t); resolve('unknown'); } });
  });
}

// ---- the request itself ----------------------------------------------------------------
// The browser's own answer to getCurrentPosition is the only source of truth: it shows the
// native prompt if the user hasn't decided, succeeds silently if allowed, and fails at once
// with code 1 if blocked. (The Permissions API can disagree with what iOS will really do,
// especially for home-screen apps, so it is never used to decide anything.)
//
// A request can fail for a TRANSIENT reason (code 2 "position unavailable" / code 3 "timeout").
// iOS does exactly that for the first second or two after the user taps Allow, while the
// location hardware starts up. That is not a failure: keep trying quietly, and keep a watch
// running in parallel, since the watch delivers the first fix as soon as one exists.
//
// Must be called synchronously from a tap when it may need to show the prompt.
function requestLocation(source, attempt) {
  attempt = attempt || 1;
  if (!locSupported()) { setLocProblem('unsupported'); renderLocationUI(); return; }
  if (attempt === 1) {
    const background = source === 'launch' || source === 'auto';
    if (locBusy && background && Date.now() - locBusySince < 20000) return;    // a tap always wins; background asks never stack
    locReq++;
    clearTimeout(locRetryTimer);
    locBusy = true; locBusySource = source; locBusySince = Date.now();
    startLocationWatch();                                            // parallel: also triggers the prompt, and catches the first fix
    gaEvent('loc_requested', { source });
  }
  const req = locReq;
  renderLocationUI();
  // coarse + cached first (fast), GPS on the second try, then coarse again
  const opts = attempt === 2
    ? { enableHighAccuracy: true, timeout: 20000, maximumAge: 600000 }
    : { enableHighAccuracy: false, timeout: 15000, maximumAge: 120000 };
  navigator.geolocation.getCurrentPosition(
    pos => {
      if (req !== locReq) return;
      locBusy = false;
      onLocationFix(pos, source);
    },
    err => {
      if (req !== locReq) return;                                    // a newer request or a fix already took over
      if (err.code !== 1 && attempt <= LOC_RETRY_MS.length) {        // transient: try again quietly
        locRetryTimer = setTimeout(() => requestLocation(source, attempt + 1), LOC_RETRY_MS[attempt - 1]);
        return;
      }
      locBusy = false;
      onLocationError(err, source);
    },
    opts
  );
}

function onLocationFix(pos, source) {
  const first = !locFixAt;
  const hadProblem = !!locProblem;
  const workedBefore = lsGet(LOC_EVER_KEY, '') === '1';       // read BEFORE it is set below
  locReq++;                                   // any retry still pending is now pointless
  clearTimeout(locRetryTimer);
  locBusy = false;
  const acc = pos.coords.accuracy;
  locAccuracy = acc;
  locFixAt = Date.now();
  locPerm = 'granted';
  lsSet(LOC_EVER_KEY, '1');
  locProblem = acc > LOC_IMPRECISE_M ? 'imprecise' : null;
  if (locFirstAccuracy === null) locFirstAccuracy = acc;

  updateUserLocation(pos);                                   // marker, first-fix centring, auto-parking + street name hooks
  if (!locAttributed) { locAttributed = true; attributePosterScan(pos.coords.latitude, pos.coords.longitude); }
  // an approximate first fix followed by a precise one: centre on the precise one, once
  if (!locRefined && locFirstAccuracy > LOC_GOOD_M && acc <= 300) { locRefined = true; map.setView([userLat, userLon], 16); }

  if (source === 'tap' || source === 'banner' || source === 'retry') {
    map.flyTo([userLat, userLon], Math.max(map.getZoom(), 16), { duration: 0.7 });
  }
  if (first) gaEvent('loc_granted', { source, accuracy_m: Math.round(acc) });
  if (hadProblem && !locProblem && source !== 'watch') showSnack('Location is on. Showing spots near you.');

  stopProbeLoop();
  if (hadProblem && locStepsKind !== 'reprompt') closeLocSteps();     // (the periodic fixes must not close a tip that is being read)
  maybeDemoPin(pos.coords.latitude, pos.coords.longitude, acc);
  renderLocationUI();

  // It worked on an earlier launch but the phone had to ask again: that is the iPhone setting, which a website can't
  // change. Say so once, and point at the one place that controls it.
  if (first && workedBefore && locPermAtLaunch === 'prompt' && isIosDevice() && !lsGet(LOC_TIP_KEY, '')) {
    lsSet(LOC_TIP_KEY, '1');
    gaEvent('loc_reprompt_detected', { standalone: isStandalone() });
    setTimeout(() => { if (!locProblem) showLocSteps('reprompt'); }, 2200);
  }
}

function onLocationError(err, source) {
  const kind = err.code === 1 ? 'denied' : (err.code === 2 ? 'unavailable' : 'timeout');
  const repeat = locProblem === kind;
  if (!repeat) gaEvent('loc_error', { code: err.code, source });
  if (err.code === 1) locPerm = 'denied';
  setLocProblem(kind);
  locReq++; clearTimeout(locRetryTimer); locBusy = false;
  // Quiet at launch (the bar says it). But when the person TRIES to use location, always answer them, even if the
  // problem was already known: that is exactly when they need to hear it.
  const asked = source === 'tap' || source === 'banner' || source === 'retry';
  if (asked) {
    if (err.code === 1) warnBlocked(source);
    else if (err.code === 2) showSnack('Can’t get your position. Check that Location Services is on.', 5000);
    else showSnack('Couldn’t find you yet. Try near a window, or tap again.', 5000);
  }
  startProbeLoop();
  renderLocationUI();
}

// "Location is blocked": a message plus the steps to fix it. Safe to call twice for one tap.
function warnBlocked(source) {
  if (Date.now() - locWarnAt < 1500) return;
  locWarnAt = Date.now();
  showSnack(source === 'retry' ? 'Location still looks blocked. Check the switch and try again.' : 'Location is blocked for this app. Here’s how to turn it on.', 5000);
  if (!document.getElementById('loc-steps').classList.contains('open')) showLocSteps();
}

function setLocProblem(p) { locProblem = p; }

// ---- keeping it alive ------------------------------------------------------------------
function startLocationWatch() {
  if (locWatchId !== null || !locSupported()) return;
  locWatchId = navigator.geolocation.watchPosition(
    pos => onLocationFix(pos, 'watch'),
    err => {
      if (err.code !== 1) return;                          // 2 / 3 are transient: keep watching
      stopLocationWatch();
      if (!locBusy) onLocationError(err, 'watch');         // revoked mid-session; if a request is running, its own error handler reports it
    },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 30000 }
  );
}
function stopLocationWatch() {
  if (locWatchId !== null) { try { navigator.geolocation.clearWatch(locWatchId); } catch (e) {} locWatchId = null; }
}

// Settings changed / app resumed: look again without bothering the user.
function refreshLocationState() {
  if (!locSupported() || locBusy) return;
  queryLocPermission().then(st => { locPerm = st; });                    // informational, and re-hooks onchange
  if (!locFixAt || Date.now() - locFixAt > 30000) requestLocation('auto');
}

// While blocked / failing, quietly try again every few seconds so that turning it on in Settings
// "just works" the moment they come back. (No prompt can appear in these states.)
function startProbeLoop() {
  if (probeTimer) return;
  probeTimer = setInterval(() => {
    const failing = ['denied', 'stuck', 'timeout', 'unavailable'].includes(locProblem);
    if (document.hidden || locBusy || !failing || !locSupported()) return;
    navigator.geolocation.getCurrentPosition(
      pos => { onLocationFix(pos, 'probe'); startLocationWatch(); },
      () => {},
      { enableHighAccuracy: false, timeout: 5000, maximumAge: 60000 }
    );
  }, 6000);
}
function stopProbeLoop() { if (probeTimer) { clearInterval(probeTimer); probeTimer = null; } }

// iOS suspends location updates while the app is in the background and often doesn't resume them.
function onAppResumed() {
  if (document.hidden) return;
  refreshLocationState();
  if (locFixAt && Date.now() - locFixAt > 45000) {
    stopLocationWatch();
    startLocationWatch();
    navigator.geolocation.getCurrentPosition(pos => onLocationFix(pos, 'resume'), () => {},
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 15000 });
  }
}

// ---- the arrow button ------------------------------------------------------------------
function locateMe() {
  // Known blocked: never fly to an old position as if all were well (it may be stale, or permission was just revoked).
  if (locProblem !== 'denied' && userLat != null && userLon != null) {
    map.flyTo([userLat, userLon], Math.max(map.getZoom(), 16), { duration: 0.7 });   // instant: go to the last known spot
    if (Date.now() - locFixAt > 60000) requestLocation('tap');                          // ...and refresh it
    return;
  }
  requestLocation('tap');          // synchronous inside the tap: this is what makes the iOS prompt appear
  // If it was just switched on in Settings this succeeds at once and no warning is needed. A blocked phone refuses at
  // once and the error handler warns; this covers a phone that doesn't answer.
  if (locProblem === 'denied') setTimeout(() => { if (locProblem === 'denied') warnBlocked('tap'); }, 600);
}
function initGeolocation() { requestLocation('legacy'); }

// ---- UI: the (small, persistent) bottom message, and the steps ---------------------------------
function platformTip() {
  if (isIosDevice()) return 'When your iPhone asks, tap Allow.';
  if (isAndroidDevice()) return 'When asked, tap Allow.';
  return 'When your browser asks, click Allow.';
}

function bannerModel() {
  if (locFixAt && !locProblem) return null;                  // we know where they are: nothing to say
  // right after launch the system prompt is on screen: say nothing until it has been answered
  if (locBusy) {
    if (locBusySource === 'launch' || locBusySource === 'auto') return null;
    return { key: 'busy', title: 'Finding you…', body: platformTip(), cta: null };
  }
  if (locProblem === 'unsupported') return { key: 'unsupported', title: 'Location isn’t available', body: 'Open parkaway in Safari or Chrome.', cta: null };
  if (locProblem === 'denied') return { key: 'denied', title: 'Turn on location', body: 'to see parking spots near you', cta: 'How' };
  if (locProblem === 'imprecise') return { key: 'imprecise', title: 'Location is approximate', body: 'Turn on Precise Location', cta: 'How' };
  if (locProblem) return { key: 'retry', title: 'Can’t find you yet', body: 'Check that Location Services is on', cta: 'Try again' };
  return { key: 'prompt', title: 'Turn on location', body: 'to see parking spots near you', cta: 'Turn on' };
}

function renderLocationUI() {
  const ok = locFixAt > 0 && !locProblem;
  const model = bannerModel();
  document.body.classList.toggle('loc-ok', ok);
  document.body.classList.toggle('loc-banner', !!model);

  const key = model ? model.key : '';
  if (key !== lastBannerKey) {
    lastBannerKey = key;
    if (model) {
      document.getElementById('loc-banner-title').textContent = model.title;
      document.getElementById('loc-banner-body').textContent = model.body;
      const cta = document.getElementById('loc-banner-cta');
      cta.textContent = model.cta || '';
      cta.classList.toggle('hidden', !model.cta);
      gaEvent('loc_banner_shown', { kind: key });
    }
  }
  document.getElementById('loc-banner').setAttribute('aria-hidden', model ? 'false' : 'true');

  // the top header and the arrow button quietly say "off" until it is solved
  const label = document.getElementById('loc-label-text');
  document.getElementById('locate-btn').classList.toggle('busy', locBusy && locBusySource !== 'launch' && locBusySource !== 'auto');
  const waiting = !ok && !locProblem && locBusy;              // the system prompt is probably on screen
  const want = ok ? 'Your location' : waiting ? 'Parking in' : (locProblem === 'imprecise' ? 'Approximate location' : 'Location is off');
  document.getElementById('loc-chip').classList.toggle('off', !ok && !waiting);
  document.getElementById('locate-btn').classList.toggle('off', !ok && !waiting);
  if (label.textContent !== want) label.textContent = want;
}

function locBannerAction() {
  const m = bannerModel();
  if (!m || !m.cta) return;
  if (m.key === 'denied' || m.key === 'imprecise') showLocSteps(m.key);
  else requestLocation('banner');          // synchronous inside the tap, so iOS shows the prompt
}

function showLocSteps(kind) {
  kind = kind || 'denied';
  locStepsKind = kind;
  const precise = kind === 'imprecise';
  // Just the reason and the steps: nothing else.
  let title = 'Turn on location', cta = 'I turned it on';
  let why = 'parkaway needs your location to find parking near you.';
  let steps;
  if (isIosDevice()) {
    steps = ['Open <b>Settings</b> › <b>Privacy &amp; Security</b> › <b>Location Services</b>',
             precise ? 'Tap <b>Safari Websites</b> and turn <b>Precise Location</b> on' : 'Tap <b>Safari Websites</b> › <b>While Using the App</b>'];
    if (kind === 'reprompt') {
      title = 'Stop the repeat question'; cta = 'Got it';
      why = 'Your iPhone asked again. One setting controls it, and websites can’t change it for you.';
      steps = ['Open <b>Settings</b> › <b>Privacy &amp; Security</b> › <b>Location Services</b>', 'Tap <b>Safari Websites</b> › <b>While Using the App</b>'];
    }
  } else if (isAndroidDevice()) {
    steps = ['Tap <b>⋮</b> › <b>Settings</b> › <b>Site settings</b> › <b>Location</b>', 'Set this site to <b>Allow</b>'];
  } else {
    steps = ['Click the <b>lock</b> icon next to the address', 'Set <b>Location</b> to <b>Allow</b>'];
  }
  document.getElementById('loc-steps-title').textContent = title;
  document.getElementById('loc-steps-done').textContent = cta;
  document.getElementById('loc-steps-note').textContent = why;
  document.getElementById('loc-steps-list').innerHTML = steps.map(s => `<li>${s}</li>`).join('');
  document.getElementById('loc-steps').classList.add('open');
  document.getElementById('loc-steps-scrim').classList.add('open');
  gaEvent('loc_steps_shown', { kind });
}

function closeLocSteps() {
  document.getElementById('loc-steps').classList.remove('open');
  document.getElementById('loc-steps-scrim').classList.remove('open');
  locStepsKind = null;
}

function locStepsDone() {
  const wasTip = locStepsKind === 'reprompt';
  closeLocSteps();
  if (!wasTip) requestLocation('retry');
}

// ---- boot --------------------------------------------------------------------------------
// No explanation screen first: ask the system straight away. If it is allowed (in this app) it
// simply works; if the user taps "Don't Allow", the small bottom message appears.
function initLocation() {
  document.addEventListener('visibilitychange', onAppResumed);
  window.addEventListener('pageshow', onAppResumed);
  if (!locSupported() || window.isSecureContext === false) { setLocProblem('unsupported'); renderLocationUI(); return; }
  requestLocation('launch');
  queryLocPermission().then(st => { locPerm = st; if (locPermAtLaunch === 'unknown') locPermAtLaunch = st; });
  // if the prompt could not be shown without a tap, the bar below offers a one-tap "Turn on"
  setTimeout(() => { if (!locFixAt && !locProblem) { locBusy = false; renderLocationUI(); } }, 10000);
}

// --------------------------------------------------------------------------
// UI controller (Yandex Go-style): bottom-sheet modes, shortcut cards,
// nudges, destination callout
// --------------------------------------------------------------------------
// The sheet (#sidebar) has three modes, driven by a class on the element:
//   mode-home    - "Where to?" and the shortcut cards
//   mode-dest    - the selected destination, its top 3 spots, and the Let's go button
//   mode-traffic - live traffic by street
// (Search is its own full-screen page now: see nav_js.js, which also owns the start screen and the route preview.)
const REDUCED_MOTION = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);
let sheetMode = 'home';

function lsGet(key, fallback) {
  try { const v = localStorage.getItem(key); return v === null ? fallback : v; } catch (e) { return fallback; }
}
function lsSet(key, value) { try { localStorage.setItem(key, value); } catch (e) {} }

// ---- Sheet modes + back button ---------------------------------------------------------------------------
// Whenever the app is NOT sitting at its start screen (map open, a destination, the traffic list, the search page),
// exactly one history entry is pushed, so "back" / swipe-back peels off ONE layer instead of leaving the app:
// maps-app sheet -> search page -> destination -> traffic -> map -> start screen. The sync is batched into a
// microtask, so several changes in one tap (close search + open map + set destination) never fight over history.
let navPushed = false;
let inPop = false;
let histQueued = false;

const atRoot = () => appScreen === 'landing' && !searchOpen && sheetMode === 'home';

function syncHistory() {
  if (inPop || histQueued) return;
  histQueued = true;
  queueMicrotask(() => {
    histQueued = false;
    if (inPop) return;
    try {
      if (!atRoot() && !navPushed) { history.pushState({ pk: 1 }, ''); navPushed = true; }
      else if (atRoot() && navPushed) { navPushed = false; history.back(); }
    } catch (e) {}
  });
}

window.addEventListener('popstate', () => {
  if (!navPushed) return;
  navPushed = false;
  inPop = true;
  try {
    if ($id('nav-sheet').classList.contains('open')) closeNavSheet();
    else if (searchOpen) closeSearchPage();
    else if (sheetMode === 'dest') clearDestination();
    else if (sheetMode !== 'home') setSheetMode('home');
    else if (appScreen === 'map') showLanding();
  } finally { inPop = false; }
  if (!atRoot()) { try { history.pushState({ pk: 1 }, ''); navPushed = true; } catch (e) {} }
});

function setSheetMode(mode) {
  const sb = document.getElementById('sidebar');
  const fromHeight = sb.offsetHeight;
  sheetMode = mode;
  sb.classList.remove('mode-home', 'mode-search', 'mode-dest', 'mode-traffic');
  sb.classList.add('mode-' + mode);
  document.body.dataset.sheet = mode;
  // Any mode other than the home view needs the sheet open.
  if (mode !== 'home') sb.classList.remove('sheet-collapsed');
  document.getElementById('sidebar-scroll').scrollTop = 0;
  syncHistory();

  // Morph the sheet between heights instead of snapping.
  const toHeight = sb.offsetHeight;
  if (!REDUCED_MOTION && fromHeight && toHeight && Math.abs(fromHeight - toHeight) > 4 && sb.animate) {
    sb.animate([{ height: fromHeight + 'px' }, { height: toHeight + 'px' }],
               { duration: 320, easing: 'cubic-bezier(0.2, 0.8, 0.2, 1)' });
  }
  if (mode === 'home') maybeShowInstallNudge();
}

function openTraffic() {
  closeMenu();
  closeLayers();
  setSheetMode('traffic');
}

// Back arrow / close: return to the destination if one is set, else home.
function closeSearchMode() {
  if (sheetMode === 'traffic') { slideOutSidebar(() => setSheetMode(currentDest ? 'dest' : 'home')); return; }
  setSheetMode(currentDest ? 'dest' : 'home');
}

function openMenu() {
  document.getElementById('menu-drawer').classList.add('open');
  document.getElementById('menu-scrim').classList.add('open');
}
function closeMenu() {
  document.getElementById('menu-drawer').classList.remove('open');
  document.getElementById('menu-scrim').classList.remove('open');
}
function openLayers() {
  closeMenu();
  document.getElementById('layers-sheet').classList.add('open');
  document.getElementById('layers-scrim').classList.add('open');
}
function closeLayers() {
  document.getElementById('layers-sheet').classList.remove('open');
  document.getElementById('layers-scrim').classList.remove('open');
}

// On phones the sheet covers the lower part of the map. Searched / shortcut / demo
// destinations are flown to the visible area above it. A pin the user dropped by tapping is
// left exactly where they tapped (the map jumping after every tap made rapid pin-dropping
// feel broken) and only nudged up if the sheet would hide it.
function centerAboveSheet(lat, lon, zoom, method) {
  if (method === 'map_click') {
    if (window.innerWidth > 768) return;
    const pt = map.latLngToContainerPoint([lat, lon]);
    const limit = window.innerHeight * 0.5;
    if (pt.y > limit) map.panBy([0, pt.y - window.innerHeight * 0.4], { animate: true, duration: 0.3 });
    return;
  }
  if (window.innerWidth > 768) { map.flyTo([lat, lon], zoom, { duration: 0.6 }); return; }
  const z = zoom || map.getZoom();
  const shift = Math.round(window.innerHeight * 0.19);
  const target = map.unproject(map.project([lat, lon], z).add([0, shift]), z);
  map.flyTo(target, z, { duration: 0.6 });
}

function formatDistance(m) {
  if (m == null || isNaN(m)) return '';
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)} m`;
  return `${(m / 1000).toFixed(1)} km`;
}

function showSnack(text, ms) {
  document.getElementById('hint-banner').classList.remove('show');     // never two messages on top of each other
  const el = document.getElementById('snack');
  el.textContent = text;
  el.classList.add('show');
  clearTimeout(showSnack._t);
  showSnack._t = setTimeout(() => el.classList.remove('show'), ms || 3500);
}

// ---- "Your location" chip ---------------------------------------------------
let lastWhere = { lat: 0, lon: 0, ts: 0 };
function updateWhere(lat, lon) {
  const now = Date.now();
  if (lastWhere.ts && haversineMeters(lat, lon, lastWhere.lat, lastWhere.lon) < 80 && now - lastWhere.ts < 120000) return;
  lastWhere = { lat, lon, ts: now };
  fetch(`/api/where?lat=${lat}&lon=${lon}`)
    .then(r => r.json())
    .then(d => {
      const street = document.getElementById('loc-street');
      document.getElementById('loc-label-text').textContent = 'Your location';
      const next = d.street || (d.in_service_area ? 'Kentron, Yerevan' : 'Outside Yerevan');
      if (street.textContent === next) return;
      street.classList.add('swap');
      setTimeout(() => { street.textContent = next; street.classList.remove('swap'); }, 180);
    })
    .catch(() => {});
}

// ---- Shortcut cards: recents + popular places, with a live parking outlook ----
const RECENTS_KEY = 'parkaway.recents';
const OUTLOOK_TEXT = { easy: 'Easy parking', moderate: 'Getting busy', tough: 'Hard to park', unknown: 'See spots' };
let placeOutlook = {};   // "lat,lon" -> outlook from /api/outlook

const placeKey = p => `${p.lat.toFixed(4)},${p.lon.toFixed(4)}`;

function loadRecents() {
  try {
    const list = JSON.parse(lsGet(RECENTS_KEY, '[]'));
    return list.filter(r => r && typeof r.name === 'string' && isFinite(r.lat) && isFinite(r.lon)).slice(0, 6);
  } catch (e) { return []; }
}

function saveRecent(lat, lon, name) {
  const keep = loadRecents().filter(r => r.name !== name && haversineMeters(r.lat, r.lon, lat, lon) > 60);
  keep.unshift({ name, lat, lon });
  lsSet(RECENTS_KEY, JSON.stringify(keep.slice(0, 6)));
}

function quickPlaces() {
  // Recents first (that is what a returning user wants). A popular place that is also a
  // recent moves to the front instead of appearing twice.
  const recents = loadRecents().slice(0, 3).map(r => ({ ...r, recent: true }));
  const rest = PRESETS.filter(p => !recents.some(r => haversineMeters(p.lat, p.lon, r.lat, r.lon) < 80));
  return recents.concat(rest);
}

function placeButton(p, i) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'place press';
  btn.dataset.key = placeKey(p);
  btn.dataset.level = 'loading';
  btn.style.setProperty('--i', i);
  btn.innerHTML = `
    <span class="place-text"><span class="place-name">${escapeHtml(p.name)}</span><span class="place-sub">&nbsp;</span></span>
    ${p.recent ? '<span class="ico place-recent" style="--icon:var(--i-clock)"></span>' : ''}
    <svg class="place-car" aria-hidden="true"><use href="#car"/></svg>`;
  btn.onclick = () => {
    gaEvent('shortcut_tap', { place: p.name, recent: p.recent ? 1 : 0, level: btn.dataset.level });
    setDestination(p.lat, p.lon, p.name, 'preset');
  };
  return btn;
}

// The kinds of place people look for, shown right in the row of shortcuts: two destinations first, then these,
// then the rest of the destinations (small cards, so the row never feels crowded).
const PRESET_CATS = [['Food', 'food'], ['Gas', 'fuel'], ['Pharmacy', 'pharmacy'], ['Coffee', 'coffee'], ['Groceries', 'grocery']];
function categoryButton(label, icon, i) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'place place-cat press';
  btn.style.setProperty('--i', i);
  btn.innerHTML = `<span class="ico" style="--icon:var(--i-${icon})"></span><span class="place-name">${label}</span>`;
  btn.onclick = () => { gaEvent('category_tap', { category: label, from: 'sheet' }); searchFor(label); };
  return btn;
}

function renderPresets() {
  const grid = document.getElementById('presets');
  grid.innerHTML = '';
  const places = quickPlaces();
  const buttons = places.map((p, i) => placeButton(p, i));
  const cats = PRESET_CATS.map(([label, icon], i) => categoryButton(label, icon, buttons.length + i));
  [...buttons.slice(0, 2), ...cats, ...buttons.slice(2)].forEach(b => grid.appendChild(b));
  applyOutlook();
  refreshOutlook();
  if (typeof renderLandingList === 'function') { renderLandingList(); if (searchOpen && !$id('search-input').value.trim()) renderSuggest(); }
}

function applyOutlook() {
  document.querySelectorAll('#presets .place').forEach(btn => {
    const o = placeOutlook[btn.dataset.key];
    if (!o) return;
    btn.dataset.level = o.level;
    btn.querySelector('.place-sub').textContent = OUTLOOK_TEXT[o.level] || OUTLOOK_TEXT.unknown;
  });
  // the start screen and the search suggestions: a short word on the right ("Easy" / "Busy" / "Hard")
  document.querySelectorAll('#ld-list .search-item, #sp-suggest .search-item').forEach(row => {
    const o = placeOutlook[row.dataset.key];
    if (!o) return;
    row.dataset.level = o.level;
    row.querySelector('.search-item-dist').textContent = LEVEL_WORD[o.level] || '';
  });
}

let outlookInFlight = false;
function refreshOutlook() {
  if (outlookInFlight || document.hidden) return;
  const pts = quickPlaces().map(p => `${p.lat},${p.lon}`).join('|');
  outlookInFlight = true;
  fetch(`/api/outlook?pts=${encodeURIComponent(pts)}`)
    .then(r => r.json())
    .then(data => {
      (data.places || []).forEach(o => { placeOutlook[`${o.lat.toFixed(4)},${o.lon.toFixed(4)}`] = o; });
      applyOutlook();
    })
    .catch(() => {
      // Never leave a card shimmering forever.
      document.querySelectorAll('#ld-list .search-item[data-level="loading"], #sp-suggest .search-item[data-level="loading"]').forEach(r => { r.dataset.level = 'unknown'; });
      document.querySelectorAll('#presets .place[data-level="loading"]').forEach(b => {
        b.dataset.level = 'unknown';
        b.querySelector('.place-sub').textContent = OUTLOOK_TEXT.unknown;
      });
    })
    .finally(() => { outlookInFlight = false; });
}

// ---- Recommendations: only the LAST pin's answer is ever shown ----------------------
// Tapping the map quickly used to fire one request per tap and render every response in the
// order it arrived, so the markers cycled through all the old pins before settling. Now a
// short debounce means only the last pin is requested, an in-flight request for an older pin
// is aborted, and a late response for an old pin is dropped.
let recSeq = 0, recAbort = null, recTimer = null;

function cancelRecommendations() {
  recSeq++;
  clearTimeout(recTimer);
  if (recAbort) { recAbort.abort(); recAbort = null; }
}

function fetchRecommendations(lat, lon) {
  cancelRecommendations();
  const seq = recSeq;
  recTimer = setTimeout(() => {
    recAbort = new AbortController();
    fetch(`/api/recommend?lat=${lat}&lon=${lon}`, { cache: 'no-store', signal: recAbort.signal })
      .then(r => { if (!r.ok) throw new Error('recommend ' + r.status); return r.json(); })
      .then(data => {
        if (seq !== recSeq || !currentDest) return;       // a newer pin (or Clear) happened meanwhile
        renderRecommendations(data.recommendations);
      })
      .catch(err => {
        if (err && err.name === 'AbortError') return;
        if (seq !== recSeq || !currentDest) return;
        document.getElementById('rec-list').innerHTML = '<div id="rec-empty">Couldn’t load parking spots. Tap the map to try again.</div>';
        document.getElementById('dest-sub').textContent = 'Couldn’t load spots';
      });
  }, 140);
}

// Which recommendation is highlighted (yellow). Starts on the best match; tapping #2 or #3
// (or their map pins) moves the highlight, while the "Best match" tag stays on #1.
function selectRec(i) {
  selectedRec = i;
  document.querySelectorAll('#rec-list .rec-card').forEach((c, k) => c.classList.toggle('selected', k === i));
  recMarkers.forEach((m, k) => {
    m.setZIndexOffset(k === i ? 700 : 200);
    const el = m.getElement && m.getElement();
    if (el) el.classList.toggle('selected', k === i);
  });
}

// Called at the end of renderRecommendations(). Tapping a card or its pin CHOOSES that spot: it is highlighted and the
// route preview from you to it is drawn (chooseRec in nav_js.js). Until then the best match is highlighted, no route.
function onRecommendationsRendered(recs) {
  lastRecs = recs || [];
  recMarkers.forEach((m, k) => m.on('click', () => chooseRec(k)));
  document.querySelectorAll('#rec-list .rec-card').forEach((c, k) => c.addEventListener('click', () => chooseRec(k)));
  selectRec(0);
  $id('go-bar').classList.toggle('hidden', !lastRecs.length);
}

// ---- First run: show how the app works with a pin on the user's own location --------
// The first time someone allows location, drop a pin exactly where they are and show the
// best parking nearby, so the product demonstrates itself before they have to do anything.
function maybeDemoPin(lat, lon, accuracy) {
  if (lsGet('parkaway.demoDone', '') || maybeDemoPin._scheduled) return;
  if ((parseInt(lsGet('parkaway.dests', '0'), 10) || 0) > 0) return;     // they already know how it works
  if (currentDest || isAdminMode || sheetMode !== 'home' || appScreen !== 'map') return;
  if (accuracy > LOC_GOOD_M) return;                                       // an approximate fix would put the pin in the wrong place: wait for a better one
  if (haversineMeters(lat, lon, CENTER[0], CENTER[1]) > 8000) return;      // not in Yerevan: nothing to show
  maybeDemoPin._scheduled = true;
  lsSet('parkaway.demoDone', '1');
  setTimeout(() => {
    if (currentDest) return;
    setDestination(lat, lon, 'Your location', 'demo');
    showSnack('Here’s how it works: your pin and the best parking nearby. Tap the map to drop another.', 6500);
  }, 900);
}

// ---- Destination: callout pin, skeletons, labels -------------------------------
function shortLabel(label) {
  return label.length > 22 ? label.slice(0, 21) + '…' : label;
}

// Yandex Go's "Pickup ~3 min" card, as a map pin.
function destCalloutHtml(label) {
  return `<div class="dest-callout"><div class="dc-ico"></div><div class="dc-text"><b>${escapeHtml(shortLabel(label))}</b><span id="dc-sub">Finding spots…</span></div></div><div class="dc-stem"></div><div class="dc-dot"></div>`;
}

function showRecSkeleton() {
  clearRoute();
  $id('go-bar').classList.add('hidden');
  lastRecs = [];
  recMarkers.forEach(m => map.removeLayer(m));
  recMarkers = [];
  const row = '<div class="rec-skel"><i></i><b></b><u></u></div>';
  document.getElementById('rec-list').innerHTML = row + row + row;
  document.getElementById('dest-sub').textContent = 'Finding the best spots…';
}

// Called from setDestination() once the destination is placed.
function onDestinationSet(lat, lon, label, method) {
  if (appScreen !== 'map') enterMapMode({ quiet: true });          // picked from the start screen: open the map first
  expandSheet();                                                    // a new destination always opens the sheet in full
  const input = document.getElementById('search-input');
  if (method !== 'search') { input.value = ''; document.getElementById('search-clear-btn').classList.add('hidden'); }
  if (method === 'search' || method === 'preset') saveRecent(lat, lon, label);
  lsSet('parkaway.dests', String((parseInt(lsGet('parkaway.dests', '0'), 10) || 0) + 1));
  document.getElementById('dest-coords').title = `${lat.toFixed(5)}, ${lon.toFixed(5)}`;

  showRecSkeleton();
  setSheetMode('dest');
  centerAboveSheet(lat, lon, (method === 'map_click') ? map.getZoom() : (method === 'demo' ? 17 : 16), method);

  // A dropped pin has no name: borrow the nearest street (debounced, and ignored if the pin moved on).
  clearTimeout(onDestinationSet._t);
  if (method === 'map_click') {
    onDestinationSet._t = setTimeout(() => {
      fetch(`/api/where?lat=${lat}&lon=${lon}`).then(r => r.json()).then(d => {
        if (!currentDest || currentDest.lat !== lat || currentDest.lon !== lon || !d.street) return;
        currentDest.label = `Near ${d.street}`;
        document.getElementById('dest-coords').innerText = currentDest.label;
        const b = document.querySelector('.dest-callout .dc-text b');
        if (b) b.textContent = shortLabel(currentDest.label);
      }).catch(() => {});
    }, 250);
  }
}

// Called from clearDestination().
function onDestinationCleared() {
  cancelRecommendations();
  clearRoute();
  lastRecs = [];
  $id('go-bar').classList.add('hidden');
  clearTimeout(onDestinationSet._t);
  document.getElementById('search-input').value = '';
  document.getElementById('search-clear-btn').classList.add('hidden');
  setSheetMode('home');
  renderPresets();
}

// Called from renderRecommendations(): headline numbers for the header + the map callout.
function updateDestSummary(recs) {
  const sub = document.getElementById('dest-sub');
  const dc = document.getElementById('dc-sub');
  if (!recs || !recs.length) {
    sub.textContent = 'No spots within range';
    if (dc) dc.textContent = 'No spots nearby';
    return;
  }
  const best = recs[0];
  sub.textContent = `${recs.length} spot${recs.length > 1 ? 's' : ''} · best is ~${best.walk_time_min} min walk`;
  if (dc) dc.textContent = `Best spot ~${best.walk_time_min} min walk`;
}

// ---- Parking segments: slim, zoom-aware, ONE canvas, one visibility switch ---------
// Everything parking-related on the map (segment lines, lot outlines and the little "P"
// badges) is drawn on a single <canvas> instead of hundreds of SVG paths and DOM markers.
// That is what keeps pinch-zooming smooth on iOS: zero extra DOM nodes, no per-frame
// reprojection of SVG, no duplicated "hit" layer. Looks the same, costs a fraction.
//   - lines are thin (2-4.5px, growing with zoom) and semi-transparent
//   - tap tolerance is only 4px beyond the line, so dropping a pin next to a segment works
//   - a lot's FILL is not tappable (only its badge/outline), so big lots don't swallow taps
const SEG_PREF_KEY = 'parkaway.segments';
let parkingVisible = lsGet(SEG_PREF_KEY, 'on') !== 'off';
let parkingVisual = null;
let parkingCanvas = null, parkingSvg = null, lastParkingWeight = null;

function getParkingRenderer() {
  // Admin curation edits shapes with Geoman, which expects SVG, so it gets the SVG renderer.
  if (isAdminMode) return parkingSvg || (parkingSvg = L.svg());
  return parkingCanvas || (parkingCanvas = L.canvas({ padding: 0.1, tolerance: 4 }));
}

function parkingWeight(z) {
  return z <= 13 ? 1.6 : z <= 14 ? 2 : z <= 15 ? 2.5 : z <= 16 ? 3 : z <= 17 ? 3.5 : 4.5;
}

function parkingStyle(feature) {
  const color = feature.properties.color || '#7f8c8d';
  if (feature.geometry.type.includes('Polygon')) {
    return { color, weight: 1.5, opacity: 0.75, fill: true, fillColor: color, fillOpacity: 0.1, lineJoin: 'round',
             interactive: isAdminMode };      // outline only; the badge is the tap target
  }
  const w = isAdminMode ? Math.max(5, parkingWeight(map.getZoom())) : parkingWeight(map.getZoom());
  return { color, weight: w, opacity: 0.8, fill: false, lineCap: 'round', lineJoin: 'round', interactive: true };
}

// The "P" badge on a lot, drawn on the canvas (a DOM marker per lot made zooming janky).
L.LotBadge = L.CircleMarker.extend({
  options: { radius: 10, bubblingMouseEvents: false, stroke: false },
  _shown() { return this._map && this._map.getZoom() >= 15; },
  _containsPoint(p) { return this._shown() && L.CircleMarker.prototype._containsPoint.call(this, p); },
  _updatePath() {
    const r = this._renderer;
    if (r && r._updateLotBadge) r._updateLotBadge(this); else if (r) r._updateCircle(this);
  }
});
L.Canvas.include({
  _updateLotBadge(layer) {
    if (!this._drawing || layer._empty() || !layer._shown()) return;
    const ctx = this._ctx, p = layer._point, s = 20, r = 6, x = p.x - s / 2, y = p.y - s / 2;
    ctx.save();                    // canvas state leaks between shapes: start from a clean, opaque state
    ctx.globalAlpha = 1;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + s, y, x + s, y + s, r);
    ctx.arcTo(x + s, y + s, x, y + s, r);
    ctx.arcTo(x, y + s, x, y, r);
    ctx.arcTo(x, y, x + s, y, r);
    ctx.closePath();
    ctx.fillStyle = layer.options.fillColor || '#3498db';
    ctx.fill();
    ctx.lineWidth = 1.5;
    ctx.strokeStyle = 'rgba(20,21,26,.9)';
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = "700 12px Inter, sans-serif";
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('P', p.x, p.y + 0.5);
    ctx.restore();
  }
});

function restyleParking() {
  if (!parkingVisual) return;
  const w = parkingWeight(map.getZoom());
  if (w !== lastParkingWeight) { lastParkingWeight = w; parkingVisual.setStyle(parkingStyle); }   // only when the width bucket changes
}

function assembleParkingLayer(features, geo) {
  parkingVisual = geo;
  lastParkingWeight = null;
  const renderer = getParkingRenderer();
  const badges = L.layerGroup();
  geo.eachLayer(l => {
    const f = l.feature;
    if (!f || !f.geometry.type.includes('Polygon')) return;
    const c = l.getBounds().getCenter();
    const b = new L.LotBadge(c, { renderer, fillColor: f.properties.color || '#3498db' });
    // the badge opens the same popup / admin editor as the lot itself
    b.on('click', (e) => { L.DomEvent.stopPropagation(e); l.fire('click', { latlng: c, originalEvent: e.originalEvent }); });
    badges.addLayer(b);
  });
  map.off('zoomend', restyleParking);
  map.on('zoomend', restyleParking);
  return L.featureGroup([geo, badges]);
}

function renderSegmentsToggle() {
  const t = document.getElementById('segments-toggle');
  if (!t) return;
  t.setAttribute('aria-checked', String(parkingVisible));
  document.getElementById('legend').classList.toggle('dim', !parkingVisible);
}

// Admin curation needs the segments to be tappable, so it always shows them.
function applyParkingVisibility() {
  if (parkingLayer) {
    const show = parkingVisible || isAdminMode;
    if (show && !map.hasLayer(parkingLayer)) parkingLayer.addTo(map);
    else if (!show && map.hasLayer(parkingLayer)) map.removeLayer(parkingLayer);
  }
  renderSegmentsToggle();
}

function toggleSegments() {
  parkingVisible = !parkingVisible;
  lsSet(SEG_PREF_KEY, parkingVisible ? 'on' : 'off');
  applyParkingVisibility();
  gaEvent('segments_toggle', { visible: parkingVisible ? 1 : 0 });
}

// ---- Dark map, baked into the tiles --------------------------------------------------
// The dark navy look used to be a CSS filter chain (invert + hue-rotate + brightness +
// contrast + saturate) on the whole tile pane. iOS Safari re-runs that on the GPU for every
// frame of a zoom, which is a big part of the lag. Now each tile is recoloured ONCE when it
// loads (same maths as the old filter) and then behaves like a plain image.
const DARK_CSS_FILTER = 'invert(1) hue-rotate(195deg) brightness(1.02) contrast(.82) saturate(.7)';   // only used if pixels can't be read
const DARK_MATRIX = (() => {
  const a = 195 * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), sat = 0.7;
  const hue = [
    0.213 + c * 0.787 - s * 0.213, 0.715 - c * 0.715 - s * 0.715, 0.072 - c * 0.072 + s * 0.928,
    0.213 - c * 0.213 + s * 0.143, 0.715 + c * 0.285 + s * 0.140, 0.072 - c * 0.072 - s * 0.283,
    0.213 - c * 0.213 - s * 0.787, 0.715 - c * 0.715 + s * 0.715, 0.072 + c * 0.928 + s * 0.072
  ];
  const sa = [
    0.213 + 0.787 * sat, 0.715 - 0.715 * sat, 0.072 - 0.072 * sat,
    0.213 - 0.213 * sat, 0.715 + 0.285 * sat, 0.072 - 0.072 * sat,
    0.213 - 0.213 * sat, 0.715 - 0.715 * sat, 0.072 + 0.928 * sat
  ];
  return { hue, sa, bright: 1.02, contrast: 0.82 };
})();

function darkenPixels(data) {
  const { hue: H, sa: S, bright, contrast } = DARK_MATRIX;
  const cl = v => (v < 0 ? 0 : v > 1 ? 1 : v);
  for (let i = 0; i < data.length; i += 4) {
    const r0 = 1 - data[i] / 255, g0 = 1 - data[i + 1] / 255, b0 = 1 - data[i + 2] / 255;        // invert
    let r = cl(H[0] * r0 + H[1] * g0 + H[2] * b0);                                                // hue-rotate
    let g = cl(H[3] * r0 + H[4] * g0 + H[5] * b0);
    let b = cl(H[6] * r0 + H[7] * g0 + H[8] * b0);
    r = cl(r * bright); g = cl(g * bright); b = cl(b * bright);                                   // brightness
    r = cl((r - 0.5) * contrast + 0.5); g = cl((g - 0.5) * contrast + 0.5); b = cl((b - 0.5) * contrast + 0.5);   // contrast
    data[i]     = cl(S[0] * r + S[1] * g + S[2] * b) * 255;                                       // saturate
    data[i + 1] = cl(S[3] * r + S[4] * g + S[5] * b) * 255;
    data[i + 2] = cl(S[6] * r + S[7] * g + S[8] * b) * 255;
  }
}

const DarkOSMLayer = L.TileLayer.extend({
  createTile(coords, done) {
    const tile = document.createElement('canvas');
    const size = this.getTileSize();
    tile.width = size.x; tile.height = size.y;
    const url = this.getTileUrl(coords);
    const paint = (img, crossOrigin) => {
      const ctx = tile.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0, size.x, size.y);
      try {
        const px = ctx.getImageData(0, 0, size.x, size.y);
        darkenPixels(px.data);
        ctx.putImageData(px, 0, 0);
      } catch (e) {
        tile.style.filter = DARK_CSS_FILTER;       // pixels not readable: fall back to the CSS filter for this tile only
      }
      done(null, tile);
    };
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => paint(img, true);
    img.onerror = () => {
      // The tile server didn't allow cross-origin reads: load it plainly and use the CSS filter on this tile.
      const plain = new Image();
      plain.onload = () => { tile.getContext('2d').drawImage(plain, 0, 0, size.x, size.y); tile.style.filter = DARK_CSS_FILTER; done(null, tile); };
      plain.onerror = (e) => done(e, tile);
      plain.src = url + (url.includes('?') ? '&' : '?') + 'plain=1';   // a different URL, so the browser's cached CORS failure isn't reused
    };
    img.src = url;
    return tile;
  }
});

function createBaseTileLayer() {
  return new DarkOSMLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    subdomains: 'abc',
    updateWhenZooming: false,      // don't fetch/paint tiles for every intermediate frame of a pinch
    keepBuffer: 2,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  });
}

// ---- Popups: dark, compact, and they never move the map --------------------------------
L.Popup.mergeOptions({ autoPan: false, className: 'pk-popup', maxWidth: 200, minWidth: 0, closeButton: false, offset: [0, -2] });

// Honest label for where the street traffic comes from (menu footer).
function updateDataSourceTag(data) {
  const el = document.getElementById('data-source-tag');
  const src = data.data_source || {};
  const names = { here: 'HERE', tomtom: 'TomTom', yandex: 'Yandex' };
  if (src.mode === 'live') el.textContent = `live traffic · ${names[src.provider] || src.provider}`;
  else if (src.mode === 'warming_up') el.textContent = 'live traffic connecting…';
  else el.textContent = document.getElementById('ytraffic-toggle') ? 'estimated traffic · real-time view: Live traffic map' : 'estimated traffic';
}

// ---- Traffic badge ------------------------------------------------------------
// Circular 0-10 traffic score + level text (home pill).
function updateTrafficBadge(data) {
  const score = data.overall_traffic_score != null
    ? data.overall_traffic_score
    : Math.max(0, Math.min(10, Math.round((data.overall_congestion_score || 0) / 10)));
  document.querySelectorAll('.traffic-score').forEach(el => {
    el.textContent = score;
    el.className = 'traffic-score lvl-' + data.overall_level;
  });
  document.querySelectorAll('.traffic-level-text').forEach(el => {
    el.textContent = data.overall_level;
  });
}

// ---- Nudges: ONE card at a time (location first, then install) -----------------
let nudgeType = null;
let deferredInstallPrompt = null;
const NUDGE_SNOOZE_MS = 7 * 24 * 3600 * 1000;

const NUDGES = {
  install:  { title: 'Add parkaway to your home screen', body: 'One tap to check parking before you leave.', cta: 'Add', icon: 'n-install' },
  ios:      { title: 'Add to your home screen', body: 'Tap the Share button, then “Add to Home Screen”.', cta: 'Got it', icon: 'n-install' }
};

function showNudge(type) {
  if (nudgeType && nudgeType !== type) return;           // never stack two nudges
  if (Date.now() < parseInt(lsGet('parkaway.snooze.' + type, '0'), 10)) return;
  nudgeType = type;
  const n = NUDGES[type];
  document.getElementById('nudge-title').textContent = n.title;
  document.getElementById('nudge-body').textContent = n.body;
  document.getElementById('nudge-cta').textContent = n.cta;
  document.getElementById('nudge-ico').className = 'nudge-ico ' + n.icon;
  document.getElementById('nudge-card').classList.add('show');
  gaEvent('nudge_shown', { type });
}

function hideNudge() {
  nudgeType = null;
  document.getElementById('nudge-card').classList.remove('show');
}

function nudgeAccept() {
  const type = nudgeType;
  gaEvent('nudge_accept', { type });
  hideNudge();
  if (type === 'install' && deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    deferredInstallPrompt.userChoice.finally(() => { deferredInstallPrompt = null; });
  } else if (type === 'ios') lsSet('parkaway.snooze.ios', String(Date.now() + 90 * 24 * 3600 * 1000));
}

function nudgeDismiss() {
  if (!nudgeType) return;
  gaEvent('nudge_dismiss', { type: nudgeType });
  lsSet('parkaway.snooze.' + nudgeType, String(Date.now() + NUDGE_SNOOZE_MS));
  hideNudge();
}

const isStandalone = () => (window.matchMedia && matchMedia('(display-mode: standalone)').matches) || window.navigator.standalone === true;
const isIosSafari = () => /iphone|ipad|ipod/i.test(navigator.userAgent) && !window.MSStream;

// Install is only worth asking after the visitor has actually got value (a destination viewed).
function maybeShowInstallNudge() {
  if (nudgeType || isStandalone()) return;
  if (!locFixAt || locProblem) return;                 // location comes first; one thing at a time
  if ((parseInt(lsGet('parkaway.dests', '0'), 10) || 0) < 1) return;
  if (deferredInstallPrompt) showNudge('install');
  else if (isIosSafari() && (parseInt(lsGet('parkaway.visits', '0'), 10) || 0) >= 2) showNudge('ios');
}

window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredInstallPrompt = e; });
window.addEventListener('appinstalled', () => { deferredInstallPrompt = null; if (nudgeType === 'install') hideNudge(); gaEvent('app_installed', {}); });

// ---- Keep the page from scrolling, and the sheet above the on-screen keyboard ---
// iOS pans the page when a text field is focused and rubber-bands it when you drag on a
// non-scrolling part of the sheet. The CSS pins the document; this covers the rest.
function syncViewport() {
  const vv = window.visualViewport;
  if (vv) {
    const root = document.documentElement.style;
    root.setProperty('--vvh', vv.height + 'px');
    root.setProperty('--vvt', vv.offsetTop + 'px');
    root.setProperty('--kb', Math.max(0, window.innerHeight - vv.height - vv.offsetTop) + 'px');
  }
  if (window.scrollX || window.scrollY) window.scrollTo(0, 0);
}
if (window.visualViewport) {
  window.visualViewport.addEventListener('resize', syncViewport);
  window.visualViewport.addEventListener('scroll', syncViewport);
}
window.addEventListener('scroll', syncViewport, { passive: true });
// Vertical drags only do something on the map and inside the sheet's own scrolling areas.
document.addEventListener('touchmove', (e) => {
  if (e.touches.length > 1) return; // pinch-zoom on the map
  if (!e.target.closest('#sidebar-scroll, #layers-sheet, #menu-drawer, #admin-modal, #admin-login-modal, #map, #mobile-sheet-handle, #search-page, #landing, #nav-sheet, #loc-steps')) {
    e.preventDefault();
  }
}, { passive: false });

// ---- Boot ---------------------------------------------------------------------
function initSheetUI() {
  // The attention cues on "Where to?" play on first load only, not every time home is shown.
  document.body.classList.add('intro');
  setTimeout(() => document.body.classList.remove('intro'), 5200);

  renderSegmentsToggle();
  // the page carries a plain class while admin mode is on, so layout rules can make room for the drawing toolbar
  const adminBtn = document.getElementById('admin-toggle');
  new MutationObserver(() => document.body.classList.toggle('admin-on', adminBtn.classList.contains('active')))
    .observe(adminBtn, { attributes: true, attributeFilter: ['class'] });
  document.getElementById('presets').addEventListener('wheel', (e) => {
    if (sheetMode !== 'home' || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
    e.currentTarget.scrollLeft += e.deltaY;
    e.preventDefault();
  }, { passive: false });
  lsSet('parkaway.visits', String((parseInt(lsGet('parkaway.visits', '0'), 10) || 0) + 1));
  initLocation();

  // Come back to the app: refresh what is shown so it never looks stale.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    refreshOutlook(); fetchTraffic(); fetchWeather();
  });
  setInterval(refreshOutlook, 60000);

  // A one-time pointer to the map's other superpower, for people who haven't used it yet.
  if (!lsGet('parkaway.hintSeen', '')) {
    setTimeout(() => {
      if (currentDest || sheetMode !== 'home' || appScreen !== 'map' || document.getElementById('snack').classList.contains('show')) return;
      const hint = document.getElementById('hint-banner');
      hint.classList.add('show');
      lsSet('parkaway.hintSeen', '1');
      setTimeout(() => hint.classList.remove('show'), 5000);
    }, 6000);
  }
}
document.addEventListener('DOMContentLoaded', initSheetUI);

// --------------------------------------------------------------------------
// Start screen, search page, route preview, hand-off to a maps app
//
//  - appScreen:   'landing' (the start screen) or 'map' (the map + bottom sheet)
//  - search page: a full-screen, TOP-anchored layer. The input is at the top, so the keyboard can never cover it,
//                 and the page is exactly as tall as the visible area, so nothing is hidden behind the keyboard.
//                 Swiping down anywhere tucks it away; swiping up still scrolls the results.
//  - route:       a preview line from you to the chosen parking spot (OpenStreetMap roads), with a light "wave"
//                 travelling along it. It is only a preview: "Let's go" hands the real navigation (turn-by-turn,
//                 live-traffic ETA) to the user's own maps app.
// --------------------------------------------------------------------------
const $id = (id) => document.getElementById(id);
let appScreen = 'landing';
let searchOpen = false;

const CATEGORIES = [
  { label: 'Food', icon: 'food' }, { label: 'Coffee', icon: 'coffee' }, { label: 'Gas', icon: 'fuel' },
  { label: 'Pharmacy', icon: 'pharmacy' }, { label: 'Groceries', icon: 'grocery' }
];
const LEVEL_WORD = { easy: 'Easy', moderate: 'Busy', tough: 'Hard' };

// ---- Screens ---------------------------------------------------------------------------------------------------
function enterMapMode(opts) {
  opts = opts || {};
  if (appScreen === 'map') return;
  appScreen = 'map';
  if (opts.instant) document.body.classList.add('no-anim');
  document.body.dataset.screen = 'map';
  if (opts.instant) requestAnimationFrame(() => requestAnimationFrame(() => document.body.classList.remove('no-anim')));
  map.invalidateSize();
  if (!opts.quiet) gaEvent('map_mode_entered', {});
  if (userLat != null && userLon != null) maybeDemoPin(userLat, userLon, locAccuracy);
  syncHistory();
}

function showLanding() {
  if (appScreen === 'landing') return;
  closeNavSheet();
  clearRoute();
  if (searchOpen) closeSearchPage();
  if (currentDest) clearDestination();                  // -> onDestinationCleared -> sheet back to home
  else if (sheetMode !== 'home') setSheetMode('home');
  appScreen = 'landing';
  document.body.dataset.screen = 'landing';
  renderLandingList();
  syncHistory();
}

// ---- Categories + the quick list (recent / popular places) -------------------------------------------------------
function renderCategories() {
  $id('ld-cats').innerHTML = CATEGORIES.map(c =>
    `<button type="button" class="ld-cat press" data-q="${c.label}"><span class="ld-cat-ico"><span class="ico" style="--icon:var(--i-${c.icon})"></span></span>${c.label}</button>`).join('');
  $id('sp-chips').innerHTML = CATEGORIES.map(c =>
    `<button type="button" class="sp-chip press" data-q="${c.label}"><span class="ico" style="--icon:var(--i-${c.icon})"></span>${c.label}</button>`).join('');
  document.querySelectorAll('.ld-cat, .sp-chip').forEach(b => b.addEventListener('click', () => {
    gaEvent('category_tap', { category: b.dataset.q });
    searchFor(b.dataset.q);
  }));
}

function searchFor(text) {
  if (!searchOpen) { openSearchPage(text, { focus: false }); return; }
  const input = $id('search-input');
  input.value = text;
  input.dispatchEvent(new Event('input'));
  input.blur();                                       // a category tap wants the results, not the keyboard
}

function fillPlaceList(container, limit) {
  container.innerHTML = '';
  quickPlaces().slice(0, limit).forEach((p) => {
    const row = document.createElement('div');
    row.className = 'search-item press';
    row.dataset.key = placeKey(p);
    row.dataset.level = 'loading';
    row.setAttribute('role', 'button');
    row.tabIndex = 0;
    row.innerHTML = `
      <div class="search-item-ico kind-${p.recent ? 'recent' : 'popular'}"></div>
      <div class="search-item-text"><div class="search-item-title">${escapeHtml(p.name)}</div><div class="search-item-sub">${p.recent ? 'Recent' : 'Popular'}</div></div>
      <div class="search-item-dist"></div>`;
    const go = () => {
      gaEvent('shortcut_tap', { place: p.name, recent: p.recent ? 1 : 0, level: row.dataset.level });
      if (searchOpen) closeSearchPage();
      setDestination(p.lat, p.lon, p.name, 'preset');
    };
    row.addEventListener('click', go);
    row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    container.appendChild(row);
  });
  applyOutlook();
}
function renderLandingList() { fillPlaceList($id('ld-list'), 4); }
function renderSuggest() { fillPlaceList($id('sp-suggest'), 6); }

// ---- Search page -----------------------------------------------------------------------------------------------
function openSearch() { openSearchPage(); }              // (the old name, still used by the sheet's buttons)

function openSearchPage(prefill, opts) {
  opts = opts || {};
  const sp = $id('search-page'), input = $id('search-input');
  if (searchOpen) { if (opts.focus !== false) input.focus({ preventScroll: true }); return; }
  searchOpen = true;
  closeMenu(); closeLayers();
  sp.style.transform = '';
  sp.classList.add('open');
  sp.setAttribute('aria-hidden', 'false');
  document.body.classList.add('search-open');
  syncViewport();
  // focus() has to happen inside the tap for iOS to raise the keyboard; the page is already full height and
  // top-anchored, so there is nothing for the keyboard to jolt or cover.
  if (opts.focus !== false && !prefill) input.focus({ preventScroll: true });
  if (typeof prefill === 'string' && prefill) {
    input.value = prefill;
    input.dispatchEvent(new Event('input'));
  } else {
    sp.classList.toggle('has-query', !!input.value.trim());
    if (!input.value.trim()) renderSuggest();
  }
  gaEvent('search_opened', {});
  syncHistory();
}

function closeSearchPage() {
  if (!searchOpen) return;
  searchOpen = false;
  const sp = $id('search-page');
  $id('search-input').blur();
  sp.classList.remove('dragging', 'open');
  sp.style.transform = '';
  sp.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('search-open');
  syncHistory();
}

// The input just changed: show suggestions (empty), a quick skeleton (waiting), or results.
function onSearchInput() {
  const v = $id('search-input').value.trim();
  const sp = $id('search-page');
  sp.classList.toggle('has-query', v.length > 0);
  if (!v) { searchSeq++; renderSuggest(); return; }
  if (v.length >= 2) showSearchSkeleton();
}

function showSearchSkeleton() {
  const dd = $id('search-dropdown');
  if (dd.querySelector('.search-item')) return;       // keep what is on screen until the new answer arrives
  dd.innerHTML = '<div class="sp-skel"><i></i><b></b></div>'.repeat(3);
  dd.classList.remove('hidden');
}

function clearSearchInput() {
  const input = $id('search-input');
  input.value = '';
  $id('search-clear-btn').classList.add('hidden');
  $id('search-dropdown').classList.add('hidden');
  $id('search-dropdown').innerHTML = '';
  $id('sp-note').classList.add('hidden');
  $id('search-page').classList.remove('has-query');
  searchSeq++;
  renderSuggest();
  input.focus({ preventScroll: true });
  searchStartedAt = null;
}

let searchSeq = 0;
async function fetchSearchResults(query) {
  if (query.length < 2) return;
  const seq = ++searchSeq;
  let url = `/api/search?q=${encodeURIComponent(query)}`;
  if (userLat != null && userLon != null) url += `&lat=${userLat}&lon=${userLon}`;
  try {
    const resp = await fetch(url);
    const data = await resp.json();
    // a slow answer must never replace the answer to what is in the box now
    if (seq !== searchSeq || $id('search-input').value.trim() !== query) return;
    renderSearchDropdown(Array.isArray(data) ? data : (data.results || []), data && data.note);
  } catch (err) {
    if (seq !== searchSeq) return;
    $id('search-dropdown').innerHTML = '<div class="search-no-results">Couldn’t search just now. Check your connection.</div>';
    $id('search-dropdown').classList.remove('hidden');
  }
}

function renderSearchDropdown(results, note) {
  const dd = $id('search-dropdown'), noteEl = $id('sp-note');
  dd.innerHTML = '';
  noteEl.textContent = note || '';
  noteEl.classList.toggle('hidden', !note);
  if (!results || !results.length) {
    dd.innerHTML = `<div class="search-no-results">${note ? escapeHtml(note) : 'Nothing found. Try a street, a place, or “food”.'}</div>`;
    noteEl.classList.add('hidden');
    dd.classList.remove('hidden');
    return;
  }
  results.forEach((item) => {
    const div = document.createElement('div');
    div.className = 'search-item';
    div.setAttribute('role', 'button');
    div.tabIndex = 0;
    const status = item.open_now === true ? '<span class="search-item-open yes">Open</span>'
                 : item.open_now === false ? '<span class="search-item-open no">Closed</span>' : '';
    div.innerHTML = `
      <div class="search-item-ico kind-${escapeHtml(item.kind || 'place')}"></div>
      <div class="search-item-text">
        <div class="search-item-title">${escapeHtml(item.title)}</div>
        <div class="search-item-sub">${escapeHtml(item.subtitle || '')}</div>
      </div>
      <div class="search-item-end"><div class="search-item-dist">${formatDistance(item.distance_m)}</div>${status}</div>`;
    div.onclick = () => selectSearchLocation(item);
    div.onkeydown = (e) => { if (e.key === 'Enter') selectSearchLocation(item); };
    dd.appendChild(div);
  });
  dd.classList.remove('hidden');
}

function selectSearchLocation(item) {
  $id('search-input').value = item.title;
  $id('search-dropdown').classList.add('hidden');
  closeSearchPage();
  if (appScreen !== 'map') enterMapMode({ quiet: true });
  map.setView([item.lat, item.lon], 16);
  setDestination(item.lat, item.lon, item.title, 'search');
}

// Swipe down ANYWHERE on the page to tuck it away. It only takes over for a clearly vertical, downward drag that
// starts where the list is already scrolled to the top; an upward swipe (scrolling to more results), a sideways
// swipe (the category chips) and a downward swipe through a list that is scrolled down all behave normally.
function setupSearchSwipe() {
  const sp = $id('search-page'), body = $id('sp-body'), input = $id('search-input');
  let g = null;
  sp.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1) { g = null; return; }
    const t = e.touches[0];
    g = { x: t.clientX, y: t.clientY, ly: t.clientY, lt: Date.now(), on: false, dy: 0, vy: 0,
          inBody: !!e.target.closest('#sp-body'), top: body.scrollTop };
  }, { passive: true });
  sp.addEventListener('touchmove', (e) => {
    if (!g || e.touches.length !== 1) return;
    const t = e.touches[0], dy = t.clientY - g.y, dx = t.clientX - g.x, now = Date.now();
    if (!g.on) {
      const vertical = Math.abs(dy) > Math.abs(dx) * 1.3;
      const listIsScrolled = g.inBody && (g.top > 0 || body.scrollTop > 0);
      if (dy > 10 && vertical && !listIsScrolled) {
        g.on = true;
        sp.classList.add('dragging');
        input.blur();                                  // the keyboard goes away with the page
      } else if (Math.abs(dx) > 12 || dy < -10 || listIsScrolled) { g = null; return; }
      else return;
    }
    e.preventDefault();
    g.dy = Math.max(0, dy);
    g.vy = (t.clientY - g.ly) / Math.max(1, now - g.lt);
    g.ly = t.clientY; g.lt = now;
    sp.style.transform = `translateY(${g.dy}px)`;
  }, { passive: false });
  const end = () => {
    if (!g) return;
    const was = g; g = null;
    if (!was.on) return;
    const dismiss = was.dy > 110 || was.vy > 0.7;
    sp.classList.remove('dragging');
    if (dismiss) closeSearchPage(); else sp.style.transform = '';
  };
  sp.addEventListener('touchend', end);
  sp.addEventListener('touchcancel', end);
}

// ---- Route preview -----------------------------------------------------------------------------------------------
let lastRecs = [];
let selectedRec = 0;
let routeSeq = 0, routeAbort = null;
const Route = { layer: null, bubble: null, bounds: null, active: false, timer: null, progUntil: 0, lastZoomAt: 0, attr: false };

const RouteLayer = L.Layer.extend({
  initialize(coords, dashed) { this._ll = coords.map(c => L.latLng(c[0], c[1])); this._dashed = !!dashed; },
  onAdd(m) {
    this._map = m;
    if (!m.getPane('route')) { const p = m.createPane('route'); p.style.zIndex = 450; p.style.pointerEvents = 'none'; }
    const pane = m.getPane('route');
    this._base = L.DomUtil.create('canvas', 'route-canvas', pane);
    this._wave = L.DomUtil.create('canvas', 'route-canvas', pane);
    this._cb = this._base.getContext('2d');
    this._cw = this._wave.getContext('2d');
    m.on('moveend zoomend resize', this._reset, this);
    m.on('zoomstart', this._hide, this);
    this._alive = true;
    this._reset();
    this._tick = this._tick.bind(this);
    requestAnimationFrame(this._tick);
  },
  onRemove(m) {
    this._alive = false;
    m.off('moveend zoomend resize', this._reset, this);
    m.off('zoomstart', this._hide, this);
    L.DomUtil.remove(this._base); L.DomUtil.remove(this._wave);
  },
  _hide() { this._paused = true; this._base.style.opacity = 0; this._wave.style.opacity = 0; },
  _reset() {
    if (!this._alive) return;
    const m = this._map, size = m.getSize(), dpr = Math.min(2, window.devicePixelRatio || 1);
    const px = Math.round(size.x * 0.25), py = Math.round(size.y * 0.25);      // drawn a little beyond the screen so a pan never shows an edge
    const w = size.x + px * 2, h = size.y + py * 2;
    this._origin = m.containerPointToLayerPoint([-px, -py]);
    for (const c of [this._base, this._wave]) {
      c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
      c.style.width = w + 'px'; c.style.height = h + 'px';
      L.DomUtil.setPosition(c, this._origin);
      c.style.opacity = 1;
    }
    this._w = w; this._h = h; this._dpr = dpr;
    this._pts = this._ll.map(ll => m.latLngToLayerPoint(ll)._subtract(this._origin));
    this._cum = [0];
    for (let i = 1; i < this._pts.length; i++) this._cum.push(this._cum[i - 1] + this._pts[i].distanceTo(this._pts[i - 1]));
    this._len = this._cum[this._cum.length - 1] || 1;
    this._drawBase();
    this._paused = false;
  },
  _path(ctx) {
    ctx.beginPath();
    this._pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)));
  },
  _drawBase() {
    const ctx = this._cb;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.setLineDash(this._dashed ? [1, 13] : []);
    this._path(ctx); ctx.strokeStyle = 'rgba(20,21,26,.82)'; ctx.lineWidth = 13; ctx.stroke();            // outline
    this._path(ctx); ctx.strokeStyle = 'rgba(245,165,54,.88)'; ctx.lineWidth = 8; ctx.stroke();           // the road
    this._path(ctx); ctx.strokeStyle = 'rgba(255,238,200,.35)'; ctx.lineWidth = 2; ctx.stroke();           // a soft highlight
    ctx.setLineDash([]);
  },
  _at(d) {                                   // point at distance d along the line
    const cum = this._cum;
    let lo = 0, hi = cum.length - 1;
    while (lo < hi - 1) { const mid = (lo + hi) >> 1; if (cum[mid] <= d) lo = mid; else hi = mid; }
    const a = this._pts[lo], b = this._pts[hi], span = (cum[hi] - cum[lo]) || 1, f = Math.max(0, Math.min(1, (d - cum[lo]) / span));
    return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
  },
  _tick(ts) {
    if (!this._alive) return;
    requestAnimationFrame(this._tick);
    if (this._dashed || REDUCED_MOTION || document.hidden || this._paused) return;
    if (ts - (this._last || 0) < 33) return;                 // ~30 frames a second is plenty and kind to batteries
    this._last = ts;
    const ctx = this._cw;
    ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
    ctx.clearRect(0, 0, this._w, this._h);
    ctx.lineCap = 'round';
    const CYCLE = 2800, total = this._len, win = Math.max(110, total * 0.24);
    const head = -win * 0.15 + ((ts % CYCLE) / CYCLE) * (total + win * 1.3);       // starts at you, runs to the spot, then starts again
    const steps = 26, step = win / steps;
    let prev = null;
    for (let k = 0; k <= steps; k++) {
      const d = head - win + k * step;
      if (d < 0 || d > total) { prev = null; continue; }
      const p = this._at(d);
      if (prev) {
        const t = (k - 0.5) / steps, a = Math.pow(Math.sin(Math.PI * t), 1.5);
        ctx.beginPath(); ctx.moveTo(prev.x, prev.y); ctx.lineTo(p.x, p.y);
        ctx.strokeStyle = `rgba(245,165,54,${(a * 0.30).toFixed(3)})`; ctx.lineWidth = 15; ctx.stroke();    // glow
        ctx.beginPath(); ctx.moveTo(prev.x, prev.y); ctx.lineTo(p.x, p.y);
        ctx.strokeStyle = `rgba(255,246,222,${(a * 0.95).toFixed(3)})`; ctx.lineWidth = 6; ctx.stroke();    // the bright crest
      }
      prev = p;
    }
  }
});

function chooseRec(i) {
  const r = lastRecs[i];
  if (!r) return;
  selectRec(i);
  gaEvent('rec_chosen', { rank: i + 1 });
  routeTo(r.location.lat, r.location.lon);
}

function routeTo(lat, lon) {
  const seq = ++routeSeq;
  if (routeAbort) routeAbort.abort();
  if (userLat == null || userLon == null || locProblem === 'denied') {
    clearRoute();
    if (!routeTo._told) { routeTo._told = true; showSnack('Turn on location to preview the route. “Let’s go” still works.', 4200); }
    return;
  }
  if (haversineMeters(userLat, userLon, lat, lon) > 120000) { clearRoute(); return; }
  routeAbort = new AbortController();
  fetch(`/api/route?from=${userLat.toFixed(6)},${userLon.toFixed(6)}&to=${lat.toFixed(6)},${lon.toFixed(6)}`, { signal: routeAbort.signal })
    .then(r => { if (!r.ok) throw new Error('route ' + r.status); return r.json(); })
    .catch((err) => {
      if (err && err.name === 'AbortError') throw err;
      const d = haversineMeters(userLat, userLon, lat, lon);
      return { coords: [[userLat, userLon], [lat, lon]], distance_m: Math.round(d * 1.3), duration_s: Math.round(d * 1.3 / 6.9), source: 'straight' };
    })
    .then(data => { if (seq === routeSeq && currentDest) showRoute(data, lat, lon); })
    .catch(() => {});
}

function clock(date) { return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }); }

function showRoute(data, lat, lon) {
  clearRoute(true);
  const coords = (data.coords && data.coords.length >= 2) ? data.coords : [[userLat, userLon], [lat, lon]];
  Route.layer = new RouteLayer(coords, data.source === 'straight').addTo(map);
  Route.bounds = L.latLngBounds(coords.map(c => L.latLng(c[0], c[1])));
  Route.active = true;
  const mins = Math.max(1, Math.round((data.duration_s || 0) / 60));
  const eta = clock(new Date(Date.now() + (data.duration_s || 0) * 1000));
  Route.bubble = L.marker([lat, lon], {
    icon: L.divIcon({ className: 'route-bubble-wrap', html: `<div class="route-bubble"><b>${data.source === 'straight' ? '~' : '≈'}${mins} min</b><span>arrive ${eta}</span></div>`, iconSize: [0, 0], iconAnchor: [0, 0] }),
    interactive: false, zIndexOffset: 1200, keyboard: false
  }).addTo(map);
  if (data.source === 'osrm' && !Route.attr) { map.attributionControl.addAttribution('Route: OSRM'); Route.attr = true; }
  fitRoute(true);
}

function clearRoute(keepSeq) {
  if (!keepSeq) { routeSeq++; if (routeAbort) { routeAbort.abort(); routeAbort = null; } }
  clearTimeout(Route.timer);
  if (Route.layer) { map.removeLayer(Route.layer); Route.layer = null; }
  if (Route.bubble) { map.removeLayer(Route.bubble); Route.bubble = null; }
  if (Route.attr) { map.attributionControl.removeAttribution('Route: OSRM'); Route.attr = false; }
  Route.active = false; Route.bounds = null;
}

function routePadding() {
  if (window.innerWidth > 768) return { tl: [$id('sidebar').offsetWidth + 50, 90], br: [60, 70] };
  return { tl: [34, 118], br: [34, $id('sidebar').offsetHeight + 40] };
}

function fitRoute(animate) {
  if (!Route.active || !Route.bounds) return;
  const pad = routePadding();
  Route.progUntil = Date.now() + (animate ? 1000 : 200);          // moves WE make must not trigger the "you panned away" refocus
  map.fitBounds(Route.bounds, { paddingTopLeft: pad.tl, paddingBottomRight: pad.br, animate: !!animate, duration: 0.6, maxZoom: 18 });
}

// Pan away from the route -> one second later it glides back. Zooming never does this, so people can look closely.
function bindRouteFollow() {
  const later = () => { clearTimeout(Route.timer); Route.timer = setTimeout(() => fitRoute(true), 1000); };
  map.on('zoomend', () => { Route.lastZoomAt = Date.now(); });
  map.on('dragstart', () => clearTimeout(Route.timer));
  // a real drag (finger or mouse) always counts, even right after a zoom
  map.on('dragend', () => { if (Route.active && Date.now() >= Route.progUntil) later(); });
  // other movement (arrow keys, the page moving the map) counts too, except the sideways drift that comes with a zoom
  map.on('moveend', () => {
    if (!Route.active || Date.now() < Route.progUntil || Date.now() - Route.lastZoomAt < 500) return;
    later();
  });
  map.getContainer().addEventListener('pointerdown', () => clearTimeout(Route.timer), { passive: true });
}

// ---- Let's go: hand the trip to a maps app ---------------------------------------------------------------------------
let navSpot = null;
const isMobileOS = () => isIosDevice() || isAndroidDevice();
const cc = (n) => +Number(n).toFixed(6);          // 6 decimals (about 10 cm): no floating-point noise in links
const NAV_APPS = [
  { key: 'yandexmaps', name: 'Yandex Maps', sub: 'Best live traffic in Yerevan',
    url: (s, f) => `https://yandex.com/maps/?rtext=${f ? `${cc(f.lat)},${cc(f.lon)}` : ''}~${cc(s.lat)},${cc(s.lon)}&rtt=auto` },
  { key: 'yandexnavi', name: 'Yandex Navigator', sub: 'Needs the Navigator app', scheme: true, mobileOnly: true,
    url: (s, f) => `yandexnavi://build_route_on_map?lat_to=${cc(s.lat)}&lon_to=${cc(s.lon)}` + (f ? `&lat_from=${cc(f.lat)}&lon_from=${cc(f.lon)}` : '') },
  { key: 'google', name: 'Google Maps',
    url: (s, f) => `https://www.google.com/maps/dir/?api=1&destination=${cc(s.lat)},${cc(s.lon)}&travelmode=driving` + (f ? `&origin=${cc(f.lat)},${cc(f.lon)}` : '') },
  { key: 'apple', name: 'Apple Maps', iosOnly: true,
    url: (s, f) => `https://maps.apple.com/?daddr=${cc(s.lat)},${cc(s.lon)}&dirflg=d` + (f ? `&saddr=${cc(f.lat)},${cc(f.lon)}` : '') },
  { key: 'waze', name: 'Waze', mobileOnly: true,
    url: (s) => `https://waze.com/ul?ll=${cc(s.lat)},${cc(s.lon)}&navigate=yes` },
  { key: 'geo', name: 'Other apps…', sub: 'Choose from your phone', scheme: true, androidOnly: true,
    url: (s) => `geo:${cc(s.lat)},${cc(s.lon)}?q=${cc(s.lat)},${cc(s.lon)}(${encodeURIComponent(s.name || 'Parking')})` }
];

function availableNavApps() {
  const last = lsGet('parkaway.navApp', '');
  const list = NAV_APPS.filter(a => !(a.iosOnly && !isIosDevice()) && !(a.androidOnly && !isAndroidDevice()) && !(a.mobileOnly && !isMobileOS()));
  return list.sort((a, b) => (b.key === last) - (a.key === last));
}

function startNav() {
  if (!currentDest || !lastRecs.length) return;
  const r = lastRecs[selectedRec] || lastRecs[0];
  navSpot = { lat: r.location.lat, lon: r.location.lon, name: r.name };
  $id('nav-sub').textContent = `Parking: ${r.name}`;
  const last = lsGet('parkaway.navApp', '');
  $id('nav-apps').innerHTML = availableNavApps().map(a => `
    <button type="button" class="nav-app" data-app="${a.key}">
      <span class="nav-app-ico"><span class="ico" style="--icon:var(--i-locate)"></span></span>
      <span class="nav-app-name">${escapeHtml(a.name)}${a.sub ? `<small>${escapeHtml(a.sub)}</small>` : ''}</span>
      ${a.key === last ? '<span class="nav-last">Last used</span>' : ''}
    </button>`).join('');
  $id('nav-apps').querySelectorAll('.nav-app').forEach(b => b.addEventListener('click', () => launchNav(b.dataset.app)));
  $id('nav-scrim').classList.add('open');
  $id('nav-sheet').classList.add('open');
  gaEvent('lets_go', { rank: selectedRec + 1 });
}

function closeNavSheet() {
  $id('nav-scrim').classList.remove('open');
  $id('nav-sheet').classList.remove('open');
}

function openExternalUrl(url, isScheme) {
  if (isScheme || !/^https?:/i.test(url)) { window.location.href = url; return; }
  const a = document.createElement('a');
  a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer';
  document.body.appendChild(a); a.click(); a.remove();
}

function launchNav(key) {
  const app = NAV_APPS.find(a => a.key === key);
  if (!app || !navSpot) return;
  const from = (userLat != null && userLon != null && locProblem !== 'denied') ? { lat: userLat, lon: userLon } : null;
  lsSet('parkaway.navApp', key);
  gaEvent('nav_launch', { app: key });
  openExternalUrl(app.url(navSpot, from), !!app.scheme);
  closeNavSheet();
  setTimeout(finishNav, 350);
  // some apps open silently, others are not installed: if we are still on screen, say what to do
  setTimeout(() => { if (!document.hidden && currentDest) showSnack('Nothing opened? That app may not be installed. Pick another.', 5000); }, 2400);
}

// Back to the three recommendations, exactly as they were first shown, ready for another spot or another place.
function finishNav() {
  clearRoute();
  if (!currentDest) return;
  selectRec(0);
  centerAboveSheet(currentDest.lat, currentDest.lon, 16, 'preset');
}

// ---- Boot ----------------------------------------------------------------------------------------------------------
function initNav() {
  renderCategories();
  renderLandingList();
  setupSearchSwipe();
  bindRouteFollow();
  $id('search-input').addEventListener('input', onSearchInput);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if ($id('nav-sheet').classList.contains('open')) closeNavSheet(); else if (searchOpen) closeSearchPage(); } });

  // the start screen mirrors the map's address header (street, weather, "location is off")
  const mirror = () => {
    $id('ld-street').textContent = $id('loc-street').textContent;
    $id('ld-weather').textContent = $id('weather-display').textContent;
    $id('ld-where-label').textContent = $id('loc-label-text').textContent;
    $id('ld-where').classList.toggle('off', $id('loc-chip').classList.contains('off'));
  };
  const mo = new MutationObserver(mirror);
  [['loc-street', { childList: true, characterData: true, subtree: true }], ['weather-display', { childList: true, characterData: true, subtree: true }],
   ['loc-label-text', { childList: true, characterData: true, subtree: true }], ['loc-chip', { attributes: true, attributeFilter: ['class'] }]]
    .forEach(([id, cfg]) => mo.observe($id(id), cfg));
  mirror();

  // Home-screen shortcuts open straight into search / traffic; ?a=map skips the start screen
  const action = new URLSearchParams(location.search).get('a');
  if (action) {
    try { history.replaceState(null, '', location.pathname); } catch (e) {}
    if (action === 'map') enterMapMode({ instant: true, quiet: true });
    else if (action === 'search') openSearchPage();
    else if (action === 'traffic') openTraffic();
  }
}
document.addEventListener('DOMContentLoaded', initNav);

// --------------------------------------------------------------------------
// Swipe-down on every menu, and gentle closing
//
//  - the bottom sheet (#sidebar): swipe anywhere on it
//        parking spots:  down -> shrinks to a small bar at the bottom   down again -> closes (back to "Where to?")
//                        up from the small bar -> opens again
//        live traffic:   down -> closes (only when its list is scrolled to the top, so scrolling still works)
//        "Where to?":    down -> peeks, up -> opens
//  - legend, "Navigate with", "Turn on location": swipe down to close
//  - the side menu: swipe left to close
//  Every close now eases away over about half a second, and a swipe carries on from wherever the finger let go.
// --------------------------------------------------------------------------
let sbSliding = false;

function safeBottomPx() {
  if (safeBottomPx._v == null) {
    const p = document.createElement('div');
    p.style.cssText = 'position:fixed;left:0;bottom:0;width:1px;height:0;padding-bottom:env(safe-area-inset-bottom,0px);visibility:hidden';
    document.body.appendChild(p);
    safeBottomPx._v = parseFloat(getComputedStyle(p).paddingBottom) || 0;
    p.remove();
  }
  return safeBottomPx._v;
}
const peekPx = () => parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--peek')) || 92;
const collapseOffset = () => Math.max(0, $id('sidebar').offsetHeight - peekPx() - safeBottomPx());
const isCollapsed = () => $id('sidebar').classList.contains('sheet-collapsed');
function collapseSheet() {
  if (sheetMode !== 'dest' && sheetMode !== 'home') return;
  const sb = $id('sidebar');
  sb.style.setProperty('--sb-off', collapseOffset() + 'px');     // (laptops: keeps the buttons beside the panel in place)
  sb.classList.add('sheet-collapsed');
}
function expandSheet() { $id('sidebar').classList.remove('sheet-collapsed'); }

// Slide the sheet right off the bottom, and only THEN change what it shows, so a close is never an instant vanish.
function slideOutSidebar(then) {
  const sb = $id('sidebar');
  if (sbSliding) return;
  sbSliding = true;
  sb.classList.remove('dragging');
  sb.style.transform = '';
  sb.classList.add('sliding-out');
  setTimeout(() => {
    try { then(); } finally { sb.classList.remove('sliding-out'); sbSliding = false; }
  }, 440);
}

function closeDestination() { slideOutSidebar(() => { expandSheet(); clearDestination(); }); }
function onDestTextTap() { if (isCollapsed()) expandSheet(); else openSearchPage(); }

function setupSheetGestures() {
  const sb = $id('sidebar'), scroll = $id('sidebar-scroll'), handle = $id('mobile-sheet-handle');
  let g = null;
  sb.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1 || sbSliding || (appScreen === 'landing' && sheetMode === 'home')) { g = null; return; }
    const t = e.touches[0];
    g = { y: t.clientY, x: t.clientX, ly: t.clientY, lt: Date.now(), on: false, v: 0, cur: 0, mode: sheetMode,
          collapsed: isCollapsed(), h: sb.offsetHeight, off: collapseOffset(),
          inScroll: !!e.target.closest('#sidebar-scroll'), top: scroll.scrollTop };
  }, { passive: true });
  sb.addEventListener('touchmove', (e) => {
    if (!g || e.touches.length !== 1) return;
    const t = e.touches[0], dy = t.clientY - g.y, dx = t.clientX - g.x, now = Date.now();
    if (!g.on) {
      const vertical = Math.abs(dy) > 10 && Math.abs(dy) > Math.abs(dx) * 1.3;
      if (!vertical) { if (Math.abs(dx) > 12) g = null; return; }
      const listScrolled = g.mode === 'traffic' && g.inScroll && (g.top > 0 || scroll.scrollTop > 0);
      let ok = false;
      if (g.mode === 'traffic') ok = dy > 0 && !listScrolled;
      else if (g.mode === 'dest' || g.mode === 'home') ok = g.collapsed ? true : dy > 0;
      if (!ok) { g = null; return; }
      g.on = true;
      sb.classList.add('dragging');
    }
    e.preventDefault();
    const base = g.collapsed ? g.off : 0;
    const canClose = g.mode === 'traffic' || (g.mode === 'dest' && g.collapsed);
    const hi = canClose ? g.h : g.off;
    let y = base + dy;
    if (y < 0) y = y * 0.25;                                  // a little give above fully open
    if (y > hi) y = hi + (y - hi) * 0.2;                      // and a firm stop where this swipe can go no further
    g.v = (t.clientY - g.ly) / Math.max(1, now - g.lt);
    g.ly = t.clientY; g.lt = now; g.cur = y;
    sb.style.transform = `translateY(${y}px)`;
  }, { passive: false });
  const end = () => {
    if (!g) return;
    const w = g; g = null;
    if (!w.on) return;
    sb.classList.remove('dragging');
    sb.style.transform = '';                                  // the CSS eases from the finger's position to wherever it settles
    let close = false;
    if (w.mode === 'traffic') close = w.cur > 90 || w.v > 0.6;
    else if (w.collapsed) {
      if (w.cur < w.off * 0.7 || w.v < -0.5) expandSheet();
      else if (w.mode === 'dest' && (w.cur > w.off + 45 || w.v > 0.5)) close = true;
    } else if (w.cur > w.off * 0.28 || w.v > 0.5) collapseSheet();
    if (close) { if (w.mode === 'traffic') closeSearchMode(); else closeDestination(); }
  };
  sb.addEventListener('touchend', end);
  sb.addEventListener('touchcancel', end);
  // tapping the tab still opens / shrinks it
  handle.addEventListener('click', () => {
    if (sheetMode !== 'home' && sheetMode !== 'dest') return;
    if (isCollapsed()) expandSheet(); else collapseSheet();
  });
}

// Bottom sheets that are plain overlays: swipe down to close (only when they are scrolled to the top).
function bindDismissSheet(el, scrim, close) {
  let g = null;
  el.addEventListener('touchstart', (e) => {
    if (!el.classList.contains('open') || e.touches.length !== 1) { g = null; return; }
    const t = e.touches[0];
    g = { y: t.clientY, x: t.clientX, ly: t.clientY, lt: Date.now(), on: false, dy: 0, v: 0, top: el.scrollTop, h: el.offsetHeight };
  }, { passive: true });
  el.addEventListener('touchmove', (e) => {
    if (!g || e.touches.length !== 1) return;
    const t = e.touches[0], dy = t.clientY - g.y, dx = t.clientX - g.x, now = Date.now();
    if (!g.on) {
      if (dy > 10 && Math.abs(dy) > Math.abs(dx) * 1.3 && g.top <= 0 && el.scrollTop <= 0) { g.on = true; el.classList.add('dragging'); }
      else if (Math.abs(dx) > 12 || dy < -10 || el.scrollTop > 0) { g = null; return; }
      else return;
    }
    e.preventDefault();
    g.dy = Math.max(0, dy);
    g.v = (t.clientY - g.ly) / Math.max(1, now - g.lt);
    g.ly = t.clientY; g.lt = now;
    el.style.transform = `translateY(${g.dy}px)`;
    if (scrim) { scrim.style.transition = 'none'; scrim.style.opacity = String(Math.max(0, 1 - (g.dy / Math.max(1, g.h)) * 1.3)); }
  }, { passive: false });
  const end = () => {
    if (!g) return;
    const w = g; g = null;
    if (!w.on) return;
    el.classList.remove('dragging');
    el.style.transform = '';
    if (scrim) { scrim.style.transition = ''; scrim.style.opacity = ''; }
    if (w.dy > 100 || w.v > 0.6) close();                      // the CSS carries on from where the finger let go
  };
  el.addEventListener('touchend', end);
  el.addEventListener('touchcancel', end);
}

// The side menu: swipe left to put it away.
function bindDrawerSwipe() {
  const el = $id('menu-drawer'), scrim = $id('menu-scrim');
  let g = null;
  el.addEventListener('touchstart', (e) => {
    if (!el.classList.contains('open') || e.touches.length !== 1) { g = null; return; }
    const t = e.touches[0];
    g = { x: t.clientX, y: t.clientY, lx: t.clientX, lt: Date.now(), on: false, dx: 0, v: 0, w: el.offsetWidth };
  }, { passive: true });
  el.addEventListener('touchmove', (e) => {
    if (!g || e.touches.length !== 1) return;
    const t = e.touches[0], dx = t.clientX - g.x, dy = t.clientY - g.y, now = Date.now();
    if (!g.on) {
      if (dx < -10 && Math.abs(dx) > Math.abs(dy) * 1.3) { g.on = true; el.classList.add('dragging'); }
      else if (Math.abs(dy) > 12 || dx > 10) { g = null; return; }
      else return;
    }
    e.preventDefault();
    g.dx = Math.min(0, dx);
    g.v = (t.clientX - g.lx) / Math.max(1, now - g.lt);
    g.lx = t.clientX; g.lt = now;
    el.style.transform = `translateX(${g.dx}px)`;
    scrim.style.transition = 'none';
    scrim.style.opacity = String(Math.max(0, 1 + (g.dx / g.w) * 1.3));
  }, { passive: false });
  const end = () => {
    if (!g) return;
    const w = g; g = null;
    if (!w.on) return;
    el.classList.remove('dragging');
    el.style.transform = '';
    scrim.style.transition = ''; scrim.style.opacity = '';
    if (w.dx < -70 || w.v < -0.5) closeMenu();
  };
  el.addEventListener('touchend', end);
  el.addEventListener('touchcancel', end);
}

document.addEventListener('DOMContentLoaded', () => {
  setupSheetGestures();
  bindDismissSheet($id('layers-sheet'), $id('layers-scrim'), closeLayers);
  bindDismissSheet($id('nav-sheet'), $id('nav-scrim'), closeNavSheet);
  bindDismissSheet($id('loc-steps'), $id('loc-steps-scrim'), closeLocSteps);
  bindDrawerSwipe();
});

// --------------------------------------------------------------------------
// Yandex live-traffic view (menu toggle, only present when YANDEX_MAPS_API_KEY is set)
//
// Why a separate page in an iframe: Yandex's free-tier terms require anything received through
// its API (they name traffic explicitly) to be shown on a Yandex map, and forbid showing Yandex
// maps through a third-party API. So the traffic layer can't go on the Leaflet map. Instead the
// toggle opens a full-screen Yandex map (/traffic-map) with Yandex's own live-traffic layer.
// Its logo and copyright stay visible at the bottom of that map, as the terms require, and the
// script only loads when someone actually turns this on.
// --------------------------------------------------------------------------
let ytFrame = null;
let ytTimer = null;
let ytLastView = null;
let ytWhy = [];                 // reasons reported by the traffic page (blocked resources, init errors)

function ytEls() {
  return {
    box: document.getElementById('ytraffic'),
    toggle: document.getElementById('ytraffic-toggle'),
    status: document.getElementById('yt-status'),
    error: document.getElementById('yt-error')
  };
}

function toggleYandexTraffic() {
  const { box } = ytEls();
  if (!box) return;
  if (box.classList.contains('open')) closeYandexTraffic(); else openYandexTraffic();
}

function openYandexTraffic() {
  const { box, toggle, status, error } = ytEls();
  if (!box || box.classList.contains('open')) return;
  closeMenu();
  closeLayers();

  const c = map.getCenter();
  const p = new URLSearchParams({ lat: c.lat.toFixed(6), lon: c.lng.toFixed(6), z: String(map.getZoom()) });
  if (userLat != null && userLon != null) { p.set('ulat', userLat.toFixed(6)); p.set('ulon', userLon.toFixed(6)); }
  if (currentDest) { p.set('dlat', currentDest.lat.toFixed(6)); p.set('dlon', currentDest.lon.toFixed(6)); p.set('dl', currentDest.label || ''); }
  if (recMarkers.length) p.set('r', recMarkers.map(m => { const ll = m.getLatLng(); return `${ll.lat.toFixed(6)},${ll.lng.toFixed(6)}`; }).join('|'));

  ytLastView = null;
  ytWhy = [];
  error.classList.remove('show');
  status.textContent = 'Loading…';
  ytFrame = document.createElement('iframe');
  ytFrame.title = 'Yandex live traffic';
  ytFrame.src = '/traffic-map?' + p.toString();
  box.querySelector('.yt-frame').appendChild(ytFrame);
  box.classList.add('open');
  toggle.setAttribute('aria-checked', 'true');
  clearTimeout(ytTimer);
  ytTimer = setTimeout(() => ytFail('timeout'), 15000);
  gaEvent('yandex_traffic_opened', {});
}

function closeYandexTraffic() {
  const { box, toggle } = ytEls();
  if (!box) return;
  clearTimeout(ytTimer);
  box.classList.remove('open');
  if (toggle) toggle.setAttribute('aria-checked', 'false');
  if (ytFrame) { ytFrame.remove(); ytFrame = null; }       // frees the map and stops its traffic refreshes
  // the user may have panned around over there: let our own map follow
  if (ytLastView && Array.isArray(ytLastView.center)) {
    map.setView(ytLastView.center, Math.max(3, Math.min(19, ytLastView.zoom || map.getZoom())), { animate: false });
  }
}

function ytFail(why) {
  const { status, error } = ytEls();
  clearTimeout(ytTimer);
  if (!error) return;
  status.textContent = 'Unavailable';
  const detail = document.getElementById('yt-detail');
  const reasons = [...new Set(ytWhy)].slice(0, 4);
  detail.textContent = reasons.length ? 'Reason: ' + reasons.join(' · ') : (why === 'timeout' ? 'Reason: Yandex did not answer in time.' : 'Reason: ' + String(why || 'unknown'));
  error.classList.add('show');
  gaEvent('yandex_traffic_error', { why: String(why || '') });
}

window.addEventListener('message', (e) => {
  if (e.origin !== location.origin || !ytFrame || e.source !== ytFrame.contentWindow) return;
  const m = e.data;
  if (!m || m.type !== 'ytraffic') return;
  const { status } = ytEls();
  if (m.event === 'ready') { clearTimeout(ytTimer); if (status.textContent === 'Loading…') status.textContent = 'Live'; }
  else if (m.event === 'level' && typeof m.level === 'number') status.textContent = `Traffic ${Math.round(m.level)}/10`;
  else if (m.event === 'view') ytLastView = m;
  else if (m.event === 'csp') {
    ytWhy.push(`blocked ${m.directive}: ${m.blocked}`);
    gaEvent('yandex_traffic_csp', { directive: String(m.directive || ''), blocked: String(m.blocked || '').slice(0, 80) });
  }
  else if (m.event === 'error') { ytWhy.push(String(m.why || 'error')); ytFail(m.why); }
});

// Escape closes whatever is open on top (handy on a laptop)
document.addEventListener('keydown', (e) => {
  if (e.key !== 'Escape') return;
  const box = document.getElementById('ytraffic');
  if (box && box.classList.contains('open')) { closeYandexTraffic(); return; }
  if (document.getElementById('loc-steps').classList.contains('open')) { closeLocSteps(); return; }
  if (document.getElementById('layers-sheet').classList.contains('open')) { closeLayers(); return; }
  if (document.getElementById('menu-drawer').classList.contains('open')) { closeMenu(); }
});
</script>
</body>
</html>
