'use client';

import { cn } from '@/lib/utils';
import { Newspaper, User, Menu, X } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from '@/components/ui/tooltip';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { name: 'Dashboard', href: '/' },
  { name: 'Screener', href: '/screener' },
];

interface TopNavProps {
  onMenuToggle?: () => void;
  isSidebarOpen?: boolean;
}

export function TopNav({ onMenuToggle, isSidebarOpen }: TopNavProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider>
      <nav className="fixed top-0 left-0 right-0 z-50 h-12 bg-background border-b border-border">
        <div className="flex items-center justify-between h-full px-4">
          {/* Left: Mobile Menu + Logo + Nav */}
          <div className="flex items-center h-full gap-6">
            {onMenuToggle && (
              <button
                onClick={onMenuToggle}
                className="lg:hidden p-1.5 -ml-1.5 text-muted-foreground hover:text-foreground duration-150 ease-out"
                aria-label={isSidebarOpen ? "Close menu" : "Open menu"}
              >
                {isSidebarOpen ? <X className="w-[18px] h-[18px]" /> : <Menu className="w-[18px] h-[18px]" />}
              </button>
            )}

            <h1 className="font-display text-lg tracking-tight">
              <span className="font-medium text-muted-foreground">Elysian</span>
              <span className="font-bold text-accent">Props</span>
            </h1>

            <div className="flex items-center h-full gap-4">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'relative flex items-center h-full text-sm font-sans border-b-2 duration-150 ease-out',
                      isActive
                        ? 'text-foreground border-accent'
                        : 'text-muted-foreground border-transparent hover:text-foreground'
                    )}
                  >
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="p-2 text-muted-foreground hover:text-foreground duration-150 ease-out">
                  <Newspaper className="w-[18px] h-[18px]" />
                </button>
              </TooltipTrigger>
              <TooltipContent>News</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="p-2 text-muted-foreground hover:text-foreground duration-150 ease-out">
                  <User className="w-[18px] h-[18px]" />
                </button>
              </TooltipTrigger>
              <TooltipContent>Profile</TooltipContent>
            </Tooltip>
          </div>
        </div>
      </nav>
    </TooltipProvider>
  );
}
