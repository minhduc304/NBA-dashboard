'use client';

import { cn } from '@/lib/utils';
import { Newspaper, User } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const leagues = [
  { name: 'NBA', active: true, beta: false }
];

export function TopNav() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 bg-background/95 backdrop-blur-sm border-b border-border">
      <div className="flex items-center justify-between h-full px-4">
        {/* Left: League Tabs */}
        <div className="flex items-center gap-1">
          {leagues.map((league) => (
            <button
              key={league.name}
              className={cn(
                'relative px-4 py-1.5 text-sm font-medium rounded-full transition-all duration-200',
                league.active
                  ? 'bg-secondary text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-secondary/50'
              )}
            >
              {league.name}
              {league.beta && (
                <Badge
                  variant="outline"
                  className="absolute -top-1 -right-2 text-[10px] px-1.5 py-0 h-4 bg-primary/20 text-primary border-primary/30"
                >
                  BETA
                </Badge>
              )}
            </button>
          ))}
        </div>

        {/* Center: Logo */}
        <div className="absolute left-1/2 -translate-x-1/2">
          <h1 className="font-[var(--font-display)] text-xl font-bold tracking-tight">
            <span className="text-foreground">Elysian</span>
            <span className="text-primary">Props</span>
          </h1>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-3">
          <button className="p-2 rounded-lg hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground">
            <Newspaper className="w-5 h-5" />
          </button>
          <button className="p-2 rounded-lg hover:bg-secondary transition-colors">
            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-primary to-primary/60 flex items-center justify-center">
              <User className="w-4 h-4 text-primary-foreground" />
            </div>
          </button>
        </div>
      </div>
    </nav>
  );
}
