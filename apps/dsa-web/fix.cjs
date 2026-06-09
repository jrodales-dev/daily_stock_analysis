const fs = require('fs');
let content = fs.readFileSync('apps/dsa-web/src/pages/HomePage.tsx', 'utf-8');

if (!content.includes('rightSidebarCollapsed')) {
    content = content.replace(
        'const [sidebarOpen, setSidebarOpen] = useState(false);',
        'const [sidebarOpen, setSidebarOpen] = useState(false);\n  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(false);'
    );
}

const topBarRegex = /<label className="flex h-10 flex-shrink-0 cursor-pointer items-center gap-1\.5 rounded-xl border border-subtle bg-surface\/60 px-3 text-xs text-secondary-text select-none transition-colors hover:border-subtle-hover hover:text-foreground">.*?<\/button>/s;

const newTopBar = `<Button
                type="button"
                variant="secondary"
                size="md"
                isLoading={isSubmittingMarketReview}
                loadingText="Enviando"
                onClick={() => void handleTriggerMarketReview()}
                className="h-10 flex-1 whitespace-nowrap md:flex-none"
              >
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
                Resumo do Mercado
              </Button>`;

content = content.replace(topBarRegex, newTopBar);

const buttonsRegex = /<div className="flex flex-wrap items-center justify-end gap-2">\s*<Button.*?<\/div>/s;
content = content.replace(buttonsRegex, '');

const rightSidebarCode = `</section>

          {/* Right Sidebar Desktop */}
          <aside className={cn(
            "hidden min-h-0 shrink-0 flex-col overflow-hidden rounded-[1.5rem] border border-[var(--shell-sidebar-border)] bg-card/72 shadow-soft-card backdrop-blur-sm transition-[width] duration-200 md:flex mt-4 mr-4 mb-4 lg:mr-8 lg:mb-6",
            rightSidebarCollapsed ? "w-[64px] p-2" : "w-[240px] lg:w-[280px] p-3"
          )}>
            <div className="flex-1 min-h-0 overflow-hidden flex flex-col gap-3">
              {/* Action Buttons */}
              {selectedReport && !isMarketReviewHistoryReport ? (
                <div className={cn("flex flex-col gap-1 shrink-0", rightSidebarCollapsed ? "items-center" : "")}>
                  <Button
                    variant="ghost"
                    size={rightSidebarCollapsed ? "icon" : "sm"}
                    disabled={isAnalyzing || selectedReport.meta.id === undefined}
                    onClick={handleReanalyze}
                    className={cn(rightSidebarCollapsed ? "h-10 w-10 shrink-0" : "w-full justify-start text-xs h-9", "hover:bg-hover hover:text-foreground")}
                  >
                    <svg className={cn("h-4 w-4 shrink-0", rightSidebarCollapsed ? "" : "mr-2")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {!rightSidebarCollapsed && reportText.reanalyze}
                  </Button>
                  <Button
                    variant="ghost"
                    size={rightSidebarCollapsed ? "icon" : "sm"}
                    disabled={selectedReport.meta.id === undefined}
                    onClick={handleAskFollowUp}
                    className={cn(rightSidebarCollapsed ? "h-10 w-10 shrink-0" : "w-full justify-start text-xs h-9", "hover:bg-hover hover:text-foreground")}
                  >
                    <svg className={cn("h-4 w-4 shrink-0", rightSidebarCollapsed ? "" : "mr-2")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    {!rightSidebarCollapsed && reportText.askFollowUp}
                  </Button>
                  <Button
                    variant="ghost"
                    size={rightSidebarCollapsed ? "icon" : "sm"}
                    disabled={selectedReport.meta.id === undefined}
                    className={cn(rightSidebarCollapsed ? "h-10 w-10 shrink-0" : "w-full justify-start text-xs h-9", "hover:bg-hover hover:text-foreground", isHistoryTrendOpen ? 'border-primary/70 bg-primary/15 text-primary shadow-glow-cyan' : undefined)}
                    onClick={() => {
                      if (isHistoryTrendOpen) {
                        closeHistoryTrend();
                        return;
                      }
                      void openHistoryTrend();
                    }}
                  >
                    <BarChart3 className={cn("h-4 w-4 shrink-0", rightSidebarCollapsed ? "" : "mr-2")} />
                    {!rightSidebarCollapsed && reportText.historyTrend}
                  </Button>
                  <Button
                    variant="ghost"
                    size={rightSidebarCollapsed ? "icon" : "sm"}
                    disabled={selectedReport.meta.id === undefined}
                    onClick={openMarkdownDrawer}
                    className={cn(rightSidebarCollapsed ? "h-10 w-10 shrink-0" : "w-full justify-start text-xs h-9", "hover:bg-hover hover:text-foreground")}
                  >
                    <svg className={cn("h-4 w-4 shrink-0", rightSidebarCollapsed ? "" : "mr-2")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {!rightSidebarCollapsed && reportText.fullReport}
                  </Button>
                </div>
              ) : null}
            </div>
            <div className="mt-auto pt-2 shrink-0">
              <button
                type="button"
                onClick={() => setRightSidebarCollapsed(!rightSidebarCollapsed)}
                className="flex h-11 w-full cursor-pointer select-none items-center justify-center rounded-xl border border-transparent px-2 text-sm text-secondary-text transition-all hover:bg-hover hover:text-foreground"
                title={rightSidebarCollapsed ? 'Expandir Painel' : 'Minimizar Painel'}
                aria-label={rightSidebarCollapsed ? 'Expandir Painel' : 'Minimizar Painel'}
              >
                {rightSidebarCollapsed ? <ChevronLeft className="h-5 w-5 shrink-0" /> : <ChevronRight className="h-5 w-5 shrink-0" />}
              </button>
            </div>
          </aside>`;

content = content.replace('</section>', rightSidebarCode);
fs.writeFileSync('apps/dsa-web/src/pages/HomePage.tsx', content, 'utf-8');
console.log('Done!');
