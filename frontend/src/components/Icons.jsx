const S = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function IconGrid(props) {
  return (
    <svg {...S} {...props}>
      <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
    </svg>
  );
}

export function IconTruck(props) {
  return (
    <svg {...S} {...props}>
      <path d="M2 7h11v8H2z" />
      <path d="M13 10h4l3 3v2h-7" />
      <circle cx="6" cy="17.2" r="1.7" />
      <circle cx="16.5" cy="17.2" r="1.7" />
    </svg>
  );
}

export function IconUsers(props) {
  return (
    <svg {...S} {...props}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.5 19c.6-3 2.8-4.6 5.5-4.6s4.9 1.6 5.5 4.6" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M15.5 14.6c2.4.2 4.3 1.6 5 4.2" />
    </svg>
  );
}

export function IconFactory(props) {
  return (
    <svg {...S} {...props}>
      <path d="M3 20.5V9.5l5.5 3.6V9.5l5.5 3.6V9.5l6 3.9v7.1z" />
      <path d="M3 20.5h18" />
    </svg>
  );
}

export function IconReceipt(props) {
  return (
    <svg {...S} {...props}>
      <path d="M6 3h12v18l-1.5-1.2L15 21l-1.5-1.2L12 21l-1.5-1.2L9 21l-1.5-1.2L6 21z" />
      <path d="M9 8h6" />
      <path d="M9 12h6" />
    </svg>
  );
}

export function IconFileCheck(props) {
  return (
    <svg {...S} {...props}>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M10 14.5l2 2 3.5-4" />
    </svg>
  );
}

export function IconSearch(props) {
  return (
    <svg {...S} {...props}>
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5.5 5.5" />
    </svg>
  );
}

export function IconBell(props) {
  return (
    <svg {...S} {...props}>
      <path d="M6.5 16.5v-6a5.5 5.5 0 0 1 11 0v6l1.6 2H4.9z" />
      <path d="M10 21.5a2.3 2.3 0 0 0 4 0" />
    </svg>
  );
}

export function IconUpload(props) {
  return (
    <svg {...S} {...props}>
      <path d="M12 16V4.5" />
      <path d="M7.5 8.5L12 4l4.5 4.5" />
      <path d="M4.5 16v3.5h15V16" />
    </svg>
  );
}

export function IconLogout(props) {
  return (
    <svg {...S} {...props}>
      <path d="M14 4.5H5.5v15H14" />
      <path d="M10.5 12H21" />
      <path d="M17.5 8.5L21 12l-3.5 3.5" />
    </svg>
  );
}

export function IconChevronLeft(props) {
  return (
    <svg {...S} {...props}>
      <path d="M14.5 5.5L8 12l6.5 6.5" />
    </svg>
  );
}

export function IconChevronRight(props) {
  return (
    <svg {...S} {...props}>
      <path d="M9.5 5.5L16 12l-6.5 6.5" />
    </svg>
  );
}

export function IconClose(props) {
  return (
    <svg {...S} {...props}>
      <path d="M6 6l12 12" />
      <path d="M18 6L6 18" />
    </svg>
  );
}

export function IconPlus(props) {
  return (
    <svg {...S} {...props}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  );
}

export function IconAlert(props) {
  return (
    <svg {...S} {...props}>
      <path d="M12 3.5L22 20H2z" />
      <path d="M12 10v4.5" />
      <path d="M12 17.2v.3" />
    </svg>
  );
}

export function IconRefresh(props) {
  return (
    <svg {...S} {...props}>
      <path d="M20 5v5h-5" />
      <path d="M4 19v-5h5" />
      <path d="M19.5 10a8 8 0 0 0-13.6-3.6L4 8" />
      <path d="M4.5 14a8 8 0 0 0 13.6 3.6L20 16" />
    </svg>
  );
}

export function IconSend(props) {
  return (
    <svg {...S} {...props}>
      <path d="M21 3L10.5 13.5" />
      <path d="M21 3l-6.8 18-3.7-7.5L3 9.8z" />
    </svg>
  );
}

export function IconMapPin(props) {
  return (
    <svg {...S} {...props}>
      <path d="M12 21s-6.5-5.3-6.5-10.2A6.5 6.5 0 0 1 19 10.8C19 15.7 12 21 12 21z" />
      <circle cx="12" cy="10.5" r="2.3" />
    </svg>
  );
}

export function IconClock(props) {
  return (
    <svg {...S} {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </svg>
  );
}

export function IconArrowLeft(props) {
  return (
    <svg {...S} {...props}>
      <path d="M20 12H4" />
      <path d="M10 6l-6 6 6 6" />
    </svg>
  );
}

export function IconBox(props) {
  return (
    <svg {...S} {...props}>
      <path d="M3.5 8L12 3.5 20.5 8v8L12 20.5 3.5 16z" />
      <path d="M3.5 8L12 12.5 20.5 8" />
      <path d="M12 12.5v8" />
    </svg>
  );
}

export function IconDoc(props) {
  return (
    <svg {...S} {...props}>
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M9.5 12h5" />
      <path d="M9.5 15.5h5" />
    </svg>
  );
}

export function IconUser(props) {
  return (
    <svg {...S} {...props}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c.8-3.4 3.4-5 7-5s6.2 1.6 7 5" />
    </svg>
  );
}

export function IconChart(props) {
  return (
    <svg {...S} {...props}>
      <path d="M4 20V11" />
      <path d="M10 20V4" />
      <path d="M16 20v-6" />
      <path d="M2.5 20h19" />
    </svg>
  );
}

export function IconInbox(props) {
  return (
    <svg {...S} {...props}>
      <path d="M4 5.5h16v13H4z" />
      <path d="M4 12.5h4.5l1.8 2.8h3.4l1.8-2.8H20" />
    </svg>
  );
}

export function IconRoute(props) {
  return (
    <svg {...S} {...props}>
      <circle cx="5.5" cy="18.5" r="2" />
      <circle cx="18.5" cy="5.5" r="2" />
      <path d="M7.6 17.5h7.4a3.4 3.4 0 0 0 0-6.8H9a3.4 3.4 0 0 1 0-6.8h7.4" />
    </svg>
  );
}

export function IconHourglass(props) {
  return (
    <svg {...S} {...props}>
      <path d="M7 3.5h10" />
      <path d="M7 20.5h10" />
      <path d="M8 3.5v3.2L12 10l4-3.3V3.5" />
      <path d="M8 20.5v-3.2L12 14l4 3.3v3.2" />
    </svg>
  );
}

export function IconBellOff(props) {
  return (
    <svg {...S} {...props}>
      <path d="M6.5 16.5v-6a5.5 5.5 0 0 1 8.7-4.5" />
      <path d="M17.5 10.5v6l1.6 2H8" />
      <path d="M10 21.5a2.3 2.3 0 0 0 4 0" />
      <path d="M3.5 3.5l17 17" />
    </svg>
  );
}
