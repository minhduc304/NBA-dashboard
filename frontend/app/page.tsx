'use client';

import { useState } from 'react';
import { TopNav } from '@/components/dashboard/TopNav';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { MainContent } from '@/components/dashboard/MainContent';
import { type Player } from '@/lib/data';

export default function Home() {
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);

  return (
    <div className="min-h-screen bg-background">
      <TopNav />
      <Sidebar
        selectedPlayer={selectedPlayer}
        onPlayerSelect={setSelectedPlayer}
      />
      <MainContent player={selectedPlayer} />
    </div>
  );
}
