<script>
  import { onMount, tick } from 'svelte';
  import gsap from 'gsap';
  import { 
    Sparkles, 
    Send, 
    FileText, 
    Folder, 
    ExternalLink, 
    Copy, 
    Check, 
    Bot, 
    User, 
    FileCode, 
    Lightbulb, 
    Database, 
    Loader2 
  } from 'lucide-svelte';

  export let onNotify = (msg) => {};
  export let onStateChange = (state) => {};

  let inputMessage = '';
  let messages = [
    {
      id: 'intro',
      role: 'assistant',
      content: "Bonjour ! Je suis ton assistant IA connecté aux fichiers de ton NAS. Demande-moi de retrouver des dossiers de projets, des factures, des devis récents ou des sauvegardes !",
      sources: []
    }
  ];
  let isGenerating = false;
  let chatEndRef;
  let chatInput;
  let copiedPath = null;

  const suggestions = [
    "Trouve les dossiers contenant 'Projet'",
    "Montre les fichiers PDF récents",
    "Où se trouvent les devis ou factures ?",
    "Cherche les fichiers Python ou de config"
  ];

  async function scrollToBottom() {
    await tick();
    if (chatEndRef) {
      chatEndRef.scrollIntoView({ behavior: 'smooth' });
    }
  }

  async function sendMessage(textToSend) {
    const text = (textToSend || inputMessage).trim();
    if (!text || isGenerating) return;

    inputMessage = '';
    const userMsgId = 'user-' + Date.now();
    const botMsgId = 'bot-' + (Date.now() + 1);

    // Ajouter message utilisateur
    messages = [
      ...messages,
      { id: userMsgId, role: 'user', content: text }
    ];

    // Initialiser bulle de l'IA
    messages = [
      ...messages,
      { id: botMsgId, role: 'assistant', content: '', sources: [], streaming: true }
    ];

    isGenerating = true;
    onStateChange('ai_thinking');
    await scrollToBottom();

    try {
      const historyPayload = messages
        .filter(m => m.id !== botMsgId && m.id !== 'intro')
        .map(m => ({ role: m.role, content: m.content }));

      const response = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: historyPayload
        })
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Erreur serveur (${response.status})`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const jsonStr = line.replace('data: ', '').trim();
          try {
            const data = JSON.parse(jsonStr);

            if (data.type === 'chunk') {
              // Filtrer le bloc ```json ... ``` de la réponse affichée si présent
              updateBotMessage(botMsgId, (prev) => {
                const nextContent = prev.content + data.text;
                return { ...prev, content: nextContent };
              });
              await scrollToBottom();
            } else if (data.type === 'sources') {
              updateBotMessage(botMsgId, (prev) => ({
                ...prev,
                sources: data.sources || []
              }));
              await scrollToBottom();
            } else if (data.type === 'error') {
              updateBotMessage(botMsgId, (prev) => ({
                ...prev,
                content: prev.content + `\n\n⚠️ ${data.message}`
              }));
            }
          } catch (e) {
            console.error('Erreur parsing SSE:', e);
          }
        }
      }

    } catch (err) {
      updateBotMessage(botMsgId, (prev) => ({
        ...prev,
        content: `❌ ${err.message || "Erreur de communication avec l'assistant."}`
      }));
    } finally {
      isGenerating = false;
      onStateChange('idle');
      updateBotMessage(botMsgId, (prev) => ({ ...prev, streaming: false }));
      await scrollToBottom();
    }
  }

  function updateBotMessage(msgId, updater) {
    messages = messages.map(m => m.id === msgId ? updater(m) : m);
  }

  // Nettoie l'affichage du message pour masquer le JSON technique brut s'il est au début
  // Nettoie l'affichage du message pour masquer le SQL et JSON technique brut
  function cleanMessageContent(raw, sources = []) {
    if (!raw) {
      if (sources && sources.length > 0) {
        return `J'ai trouvé ${sources.length} fichier(s) correspondant à votre recherche sur le NAS :`;
      }
      return '';
    }

    // 1. Masquer les blocs SQL (les fichiers sont affichés dans les cartes dédiées sous la bulle)
    let text = raw.replace(/```sql[\s\S]*?```/gi, '').trim();

    // 2. Extraire l'explication d'un éventuel bloc JSON
    const jsonMatch = text.match(/```json[\s\S]*?```/i);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0].replace(/```json|```/gi, '').trim());
        const expl = parsed.explanation || parsed.explication || parsed.message || parsed.reponse || parsed.text || '';
        text = text.replace(jsonMatch[0], expl).trim();
      } catch {
        text = text.replace(jsonMatch[0], '').trim();
      }
    }

    // 3. Si après filtrage le texte est vide mais qu'on a des fichiers sources
    if (!text) {
      if (sources && sources.length > 0) {
        return `J'ai trouvé ${sources.length} élément(s) correspondant à votre recherche sur le NAS :`;
      }
      return raw.trim() || "Voici les éléments trouvés sur votre NAS :";
    }

    return text;
  }

  async function copyPath(path) {
    try {
      await navigator.clipboard.writeText(path);
      copiedPath = path;
      onNotify('Chemin copié dans le presse-papier');
      setTimeout(() => {
        if (copiedPath === path) copiedPath = null;
      }, 2000);
    } catch (err) {
      console.error(err);
    }
  }

  async function openSourceItem(item) {
    try {
      const res = await fetch('/api/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: item.path, reveal: true })
      });
      if (res.ok) {
        onNotify(`Ouverture : ${item.name}`);
      } else {
        const err = await res.json();
        onNotify(`Erreur : ${err.detail || 'Impossible d\'ouvrir'}`);
      }
    } catch {
      onNotify('Erreur de connexion');
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  onMount(() => {
    if (chatInput) chatInput.focus();
  });
</script>

<div class="mx-auto flex h-[calc(100vh-5rem)] w-full max-w-4xl flex-col px-4 py-4 sm:px-6">

  <!-- Zone des messages du chat -->
  <div class="flex-1 overflow-y-auto pr-2 pb-4 space-y-4">
    {#each messages as msg (msg.id)}
      <div class="flex items-start gap-3.5 {msg.role === 'user' ? 'justify-end' : 'justify-start'}">
        
        <!-- Avatar Bot -->
        {#if msg.role === 'assistant'}
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-violet-600 to-indigo-500 text-white shadow-md shadow-violet-500/20">
            <Sparkles class="h-4 w-4" />
          </div>
        {/if}

        <div class="flex flex-col gap-2 max-w-[85%] sm:max-w-[75%]">
          <!-- Bulle de message -->
          <div class="glass-panel rounded-2xl p-4 text-sm leading-relaxed shadow-xl {msg.role === 'user' ? 'bg-indigo-600/20 border-indigo-500/30 text-white self-end' : 'bg-zinc-900/70 border-white/10 text-zinc-200'}">
            
            <p class="whitespace-pre-wrap">{cleanMessageContent(msg.content, msg.sources)}</p>

            {#if msg.streaming && !msg.content}
              <div class="flex items-center gap-2 text-xs text-violet-300 animate-pulse py-1">
                <Loader2 class="h-3.5 w-3.5 animate-spin" />
                <span>L'IA analyse vos fichiers NAS...</span>
              </div>
            {/if}
          </div>

          <!-- Section : Fichiers sources du NAS utilisés -->
          {#if msg.sources && msg.sources.length > 0}
            <div class="rounded-xl border border-white/5 bg-zinc-950/60 p-3 backdrop-blur-md">
              <div class="flex items-center gap-1.5 pb-2 text-[11px] font-semibold tracking-wider uppercase text-zinc-400">
                <Database class="h-3.5 w-3.5 text-indigo-400" />
                <span>Fichiers sources du NAS utilisés ({msg.sources.length}) :</span>
              </div>

              <div class="flex flex-wrap gap-2">
                {#each msg.sources as src}
                  <div class="group/src flex items-center gap-1.5 rounded-lg border border-white/10 bg-zinc-900/80 px-2.5 py-1 text-xs text-zinc-300 transition-all hover:border-indigo-500/40 hover:bg-zinc-800">
                    {#if src.is_dir}
                      <Folder class="h-3.5 w-3.5 text-amber-400 shrink-0" />
                    {:else}
                      <FileText class="h-3.5 w-3.5 text-indigo-400 shrink-0" />
                    {/if}

                    <span class="max-w-[200px] truncate font-medium text-white" title={src.name}>
                      {src.name}
                    </span>

                    <!-- Actions source -->
                    <div class="flex items-center gap-1 pl-1">
                      <button
                        on:click={() => copyPath(src.path)}
                        class="text-zinc-500 hover:text-zinc-200 transition-colors"
                        title="Copier le chemin réseau"
                      >
                        {#if copiedPath === src.path}
                          <Check class="h-3 w-3 text-emerald-400" />
                        {:else}
                          <Copy class="h-3 w-3" />
                        {/if}
                      </button>

                      <button
                        on:click={() => openSourceItem(src)}
                        class="text-zinc-500 hover:text-indigo-300 transition-colors"
                        title="Ouvrir l'emplacement"
                      >
                        <ExternalLink class="h-3 w-3" />
                      </button>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>

        <!-- Avatar User -->
        {#if msg.role === 'user'}
          <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-zinc-800 text-zinc-300 border border-white/10">
            <User class="h-4 w-4" />
          </div>
        {/if}

      </div>
    {/each}
    <div bind:this={chatEndRef}></div>
  </div>

  <!-- Suggestions de requêtes rapides (si peu de messages) -->
  {#if messages.length <= 2}
    <div class="flex flex-wrap items-center gap-2 py-2">
      <span class="flex items-center gap-1 text-[11px] text-zinc-500">
        <Lightbulb class="h-3 w-3 text-amber-400" />
        Suggestions :
      </span>
      {#each suggestions as s}
        <button
          on:click={() => sendMessage(s)}
          class="rounded-lg border border-white/5 bg-zinc-900/60 px-2.5 py-1 text-xs text-zinc-400 transition-all hover:border-violet-500/30 hover:bg-zinc-800 hover:text-zinc-200"
        >
          {s}
        </button>
      {/each}
    </div>
  {/if}

  <!-- Barre de saisie du chat -->
  <div class="relative pt-2">
    <div class="glass-panel flex items-end gap-2 rounded-2xl border border-white/10 p-2 shadow-2xl focus-within:border-violet-500/50 focus-within:ring-2 focus-within:ring-violet-500/20">
      <textarea
        bind:this={chatInput}
        bind:value={inputMessage}
        on:keydown={handleKeyDown}
        placeholder="Demandez à l'IA de retrouver des fichiers ou dossiers... (Entrée pour envoyer)"
        rows="1"
        class="max-h-32 min-h-[44px] w-full resize-none bg-transparent px-3 py-2.5 text-sm text-white placeholder-zinc-500 focus:outline-none"
      ></textarea>

      <button
        on:click={() => sendMessage()}
        disabled={!inputMessage.trim() || isGenerating}
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-md shadow-violet-500/25 transition-all hover:brightness-110 disabled:opacity-40"
        title="Envoyer"
      >
        {#if isGenerating}
          <Loader2 class="h-4 w-4 animate-spin" />
        {:else}
          <Send class="h-4 w-4" />
        {/if}
      </button>
    </div>
  </div>

</div>
