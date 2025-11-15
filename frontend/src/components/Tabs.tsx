// src/components/Tabs.tsx
export function Tabs({ tabs, active, onChange }:{tabs:string[]; active:string; onChange:(t:string)=>void}) {
  return (
    <div className="flex gap-2 mb-4">
      {tabs.map(t => (
        <button
  key={t}
  className={`px-5 py-2 rounded-full text-sm font-medium transition 
              ${t===active ? 'bg-green-700 text-white shadow-md' : 'bg-green-50 text-green-700 hover:bg-green-100'}`}
  onClick={()=>onChange(t)}
>
        {t}</button>
      ))}
    </div>
    
  );
}
