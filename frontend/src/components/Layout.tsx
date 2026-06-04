import { NavLink, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Home, Images, Settings as Cog, Camera } from "lucide-react";
import type { ReactNode } from "react";

const NAV = [
  { to: "/", label: "Dashboard", icon: Home, end: true },
  { to: "/gallery", label: "Gallery", icon: Images, end: false },
  { to: "/settings", label: "Settings", icon: Cog, end: false },
];

function NavItem({
  to,
  label,
  icon: Icon,
  end,
}: {
  to: string;
  label: string;
  icon: typeof Home;
  end: boolean;
}) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        `group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition ${
          isActive
            ? "bg-ink-800 text-white"
            : "text-neutral-400 hover:bg-ink-800/60 hover:text-neutral-100"
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={`h-5 w-5 ${isActive ? "text-ig-pink" : "text-current"}`}
            strokeWidth={2.2}
          />
          <span>{label}</span>
        </>
      )}
    </NavLink>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const location = useLocation();
  return (
    <div className="min-h-screen md:flex">
      {/* Sidebar (desktop) */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-ink-700 bg-ink-900/60 px-4 py-6 backdrop-blur md:flex">
        <div className="mb-8 flex items-center gap-3 px-1">
          <div className="ig-gradient grid h-10 w-10 place-items-center rounded-xl shadow-glow">
            <Camera className="h-5 w-5 text-white" strokeWidth={2.4} />
          </div>
          <div className="leading-tight">
            <div className="ig-gradient-text text-lg font-extrabold">UnRaiders</div>
            <div className="text-[10px] uppercase tracking-widest text-neutral-500">
              of the lost Sta
            </div>
          </div>
        </div>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavItem key={n.to} {...n} />
          ))}
        </nav>
        <div className="mt-auto px-1 text-[11px] text-neutral-600">
          Local archive · {new Date().getFullYear()}
        </div>
      </aside>

      {/* Top bar (mobile) */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-ink-700 bg-ink-900/80 px-4 py-3 backdrop-blur md:hidden">
        <div className="flex items-center gap-2">
          <div className="ig-gradient grid h-8 w-8 place-items-center rounded-lg">
            <Camera className="h-4 w-4 text-white" strokeWidth={2.4} />
          </div>
          <span className="ig-gradient-text font-extrabold">UnRaiders</span>
        </div>
      </header>

      <main className="min-w-0 flex-1 pb-24 md:pb-10">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, ease: "easeOut" }}
          className="mx-auto max-w-6xl px-4 py-6 md:px-8"
        >
          {children}
        </motion.div>
      </main>

      {/* Bottom nav (mobile) */}
      <nav className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-around border-t border-ink-700 bg-ink-900/90 py-2 backdrop-blur md:hidden">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 px-4 py-1 text-[10px] font-semibold ${
                isActive ? "text-ig-pink" : "text-neutral-400"
              }`
            }
          >
            <Icon className="h-5 w-5" strokeWidth={2.2} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
