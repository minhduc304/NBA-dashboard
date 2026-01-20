'use client';

import { useState, useCallback } from 'react';
import { TopNav } from '@/components/dashboard/TopNav';
import { Sidebar } from '@/components/dashboard/Sidebar';
import { MainContent } from '@/components/dashboard/MainContent';
import { type Player } from '@/lib/data';

export default function Home() {
  const [selectedPlayer, setSelectedPlayer] = useState<Player | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handlePlayerSelect = useCallback((player: Player) => {
    setSelectedPlayer(player);
    // Close sidebar on mobile when player is selected
    setIsSidebarOpen(false);
  }, []);

  const handleMenuToggle = useCallback(() => {
    setIsSidebarOpen(prev => !prev);
  }, []);

  const handleSidebarClose = useCallback(() => {
    setIsSidebarOpen(false);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <TopNav onMenuToggle={handleMenuToggle} isSidebarOpen={isSidebarOpen} />

      {/* Mobile backdrop overlay */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={handleSidebarClose}
          aria-hidden="true"
        />
      )}

      <Sidebar
        selectedPlayer={selectedPlayer}
        onPlayerSelect={handlePlayerSelect}
        isOpen={isSidebarOpen}
        onClose={handleSidebarClose}
      />
      <MainContent player={selectedPlayer} />
    </div>
  );
}
