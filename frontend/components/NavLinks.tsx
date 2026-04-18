"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Welcome" },
  { href: "/map", label: "Live Map" },
  { href: "/chat", label: "Concierge" },
  { href: "/ops", label: "Ops Console" },
];

export default function NavLinks() {
  const path = usePathname() || "/";
  return (
    <>
      {LINKS.map(({ href, label }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {label}
          </Link>
        );
      })}
    </>
  );
}
