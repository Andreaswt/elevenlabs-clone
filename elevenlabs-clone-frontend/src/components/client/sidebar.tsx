"use client";

import { signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";
import {
  IoChatboxOutline,
  IoMicOutline,
  IoMusicalNotesOutline,
  IoPersonOutline,
  IoPinOutline,
} from "react-icons/io5";
import { isBoxedPrimitive } from "util/types";

export default function Sidebar({ isMobile = false }: { isMobile?: boolean }) {
  const pathname = usePathname();
  const [isPinned, setIsPinned] = useState(true);
  const [isHovered, setIsHovered] = useState(false);
  const [showAccountMenu, setShowAccountMenu] = useState(false);
  const accountMenuRef = useRef<HTMLDivElement>(null);

  const isExpanded = isMobile || isPinned || isHovered;

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        accountMenuRef.current &&
        !accountMenuRef.current.contains(event.target as Node)
      ) {
        setShowAccountMenu(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  const handleSignOut = () => {
    signOut();
    setShowAccountMenu(false);
  };

  return (
    <div
      className={`${isExpanded ? "w-64" : "w-16"} flex h-full flex-col border-r border-gray-200 bg-white px-3 py-4 transition-all duration-300`}
      onMouseEnter={() => !isMobile && setIsHovered(true)}
      onMouseLeave={() => !isMobile && setIsHovered(false)}
    >
      <div className="flex items-center justify-between">
        <h1 className={`text-xl font-bold ${!isExpanded && "hidden"}`}>
          12TwelveLabs
        </h1>
        {!isMobile && (
          <button
            onClick={() => setIsPinned(!isPinned)}
            className="flex h-8 w-8 items-center justify-center rounded-lg transition-all hover:bg-gray-100"
            title={isPinned ? "Unpin sidebar" : "Pin sidebar"}
          >
            <div
              className={`flex h-8 w-8 items-center justify-center transition-all ${isPinned ? "rounded-lg bg-gray-200" : "text-gray-500"}`}
            >
              {isExpanded ? (
                <IoPinOutline className="h-5 w-5" />
              ) : (
                <div className="flex h-fit w-fit items-center justify-center rounded-lg bg-white px-3 py-2 shadow">
                  <span className="text-md font-bold text-black">12</span>
                </div>
              )}
            </div>
          </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="mt-8 flex flex-1 flex-col">
        <SectionHeader isExpanded={isExpanded}>Playground</SectionHeader>
        {/* Removed Text to Speech button for old path */}
        <SidebarButton
          icon={<IoMicOutline />} // Icon can be IoChatboxOutline or IoMicOutline, kept IoMicOutline
          isExpanded={isExpanded}
          isActive={pathname.includes("/app/speech-synthesis/main")} // Updated isActive
          href="/app/speech-synthesis/main" // Updated href
        >
          Speech Synthesis 
        </SidebarButton>
        {/* Removed Sound Effects button */}
      </nav>

      {/* Bottom Section */}
      <div className="relative mt-auto" ref={accountMenuRef}>
        <button
          onClick={() => setShowAccountMenu(!showAccountMenu)}
          className="flex w-full items-center rounded-lg px-2.5 py-2 text-sm"
        >
          <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
            <IoPersonOutline />
          </div>
          <div
            className={`ml-3 overflow-hidden text-gray-600 transition-all duration-300 ${isExpanded ? "w-auto opacity-100" : "w-0 opacity-0"}`}
            style={{ whiteSpace: "nowrap" }}
          >
            My Account
          </div>
        </button>

        {showAccountMenu && (
          <div className="absolute bottom-12 left-0 z-10 min-w-[180px] rounded-md border border-gray-200 bg-white py-1 shadow-lg">
            <button
              onClick={handleSignOut}
              className="flex w-full items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Sign out
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionHeader({
  children,
  isExpanded,
}: {
  children: ReactNode;
  isExpanded: boolean;
}) {
  return (
    <div className="mb-2 mt-4 h-6 pl-4">
      <span
        className={`text-sm text-gray-500 transition-opacity duration-200 ${isExpanded ? "opacity-100" : "opacity-0"}`}
      >
        {children}
      </span>
    </div>
  );
}

function SidebarButton({
  icon,
  children,
  isExpanded,
  isActive,
  href,
}: {
  icon: ReactNode;
  children: ReactNode;
  isExpanded: boolean;
  isActive: boolean;
  href: string;
}) {
  return (
    <Link
      href={href}
      className={`flex w-full items-center rounded-lg px-2.5 py-2 text-sm transition-colors ${isActive ? "bg-gray-100 font-medium" : "text-gray-600 hover:bg-gray-50"}`}
    >
      <div className="flex h-5 w-5 flex-shrink-0 items-center justify-center">
        {icon}
      </div>
      <div
        className={`ml-3 overflow-hidden transition-all duration-300 ${isExpanded ? "w-auto opacity-100" : "w-0 opacity-0"}`}
        style={{ whiteSpace: "nowrap" }}
      >
        {children}
      </div>
    </Link>
  );
}
