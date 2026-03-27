import ChatWidget from "@/components/ChatWidget";

export default function Home() {
  return (
    <main className="min-h-screen w-full relative overflow-hidden bg-gradient-to-br from-[#0a1628] to-[#1e3a5f]">
      {/* Decorative background elements */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-blue-500/10 blur-[120px]" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-red-500/10 blur-[120px]" />
      
      <div className="container mx-auto px-4 py-20 flex flex-col items-center justify-center min-h-screen text-center text-white relative z-10">
        <h1 className="text-5xl md:text-7xl font-bold mb-6 tracking-tight">
          GeTS <span className="text-gets-red">Holidays</span>
        </h1>
        <p className="text-xl md:text-2xl text-slate-300 max-w-2xl mx-auto leading-relaxed">
          Embark on extraordinary journeys. Discover perfectly curated tour packages and seamless travel experiences.
        </p>
        
        <div className="mt-12 flex gap-4">
          <button className="px-8 py-3 bg-gets-red hover:bg-[#b30000] text-white rounded-full font-semibold transition-all shadow-lg shadow-red-900/20">
            Explore Destinations
          </button>
          <button className="px-8 py-3 bg-white/10 hover:bg-white/20 text-white border border-white/20 rounded-full font-semibold transition-all backdrop-blur-sm">
            View Packages
          </button>
        </div>
      </div>

      {/* Floating Widget */}
      <ChatWidget />
    </main>
  );
}
