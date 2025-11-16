// src/components/Tabs.tsx
import React from "react";

type TabsProps = {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
};

export const Tabs: React.FC<TabsProps> = ({ tabs, active, onChange }) => {
  return (
    <div className="eco-tabs">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          className={`eco-tab ${active === tab ? "eco-tab--active" : ""}`}
          onClick={() => onChange(tab)}
        >
          {tab}
        </button>
      ))}
    </div>
  );
};
