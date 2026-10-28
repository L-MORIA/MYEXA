const { createApp } = Vue;

createApp({
    data() {
        return {
            searchQuery: '',
            // Languages come from GET /api/languages — the backend is the single
            // source of truth, so adding a language no longer requires editing
            // the frontend as well.
            languages: [],
            selectedLanguages: [],
            numResults: 10,
            filterByRelevance: true,
            searchCustomDB: true,
            searchResults: null,
            searchMeta: {},
            loading: false,
            activeLang: null,
            notice: null,
            customSites: [],
            uploadedFile: null,
            ocrLanguage: 'rus',
            newSite: {
                url: '',
                title: '',
                category: '',
                tags: ''
            }
        };
    },

    mounted() {
        this.loadLanguages();
        this.loadCustomSites();
    },

    computed: {
        tabs() {
            const langs = this.languages.map(l => ({ code: l.code, label: l.label }));
            return [...langs, { code: 'custom_db', label: 'Custom DB' }];
        },
        activeTabLabel() {
            const tab = this.tabs.find(t => t.code === this.activeLang);
            return tab ? tab.label : this.activeLang || '';
        },
        activeTabResults() {
            return this.searchResults?.[this.activeLang] || [];
        }
    },

    methods: {
        notify(message, type = 'error') {
            // Inline banner instead of alert(): a modal freezes the whole page
            // and blocks any further interaction.
            this.notice = { message, type };
        },
        clearNotice() {
            this.notice = null;
        },

        async loadLanguages() {
            try {
                const response = await fetch('/api/languages');
                const data = await response.json();
                if (data.success) {
                    this.languages = data.languages;
                    this.selectedLanguages = [...(data.default || [])];
                    this.activeLang = this.selectedLanguages[0] || (data.languages[0]?.code ?? null);
                }
            } catch (error) {
                console.error('Load languages error:', error);
            }
        },

        resultCount(code) {
            const list = this.searchResults?.[code];
            return Array.isArray(list) && list.length ? list.length : 0;
        },

        metaWarning(code) {
            const meta = this.searchMeta?.[code];
            if (!meta) return '';
            if (meta.error) return `Search backend error for this language: ${meta.error}`;
            if (meta.fallback_reason) {
                // The primary provider failed and the fallback answered. The
                // user must see it: the results come from a different source.
                return `Primary provider unavailable (${meta.fallback_reason}) — `
                    + 'these results come from the local fallback (SearXNG).';
            }
            if (meta.filtered_out) {
                return `All ${meta.fetched} results scored below the relevance threshold (${meta.threshold}).`;
            }
            if (meta.language_mismatched) {
                return `${meta.language_mismatched} result(s) are in another language.`;
            }
            return '';
        },

        emptyStateMessage(code) {
            // The empty state must say WHY it is empty: a provider outage and a
            // relevance threshold are completely different problems.
            const meta = this.searchMeta?.[code];
            if (meta?.error) {
                return 'The search backend did not return results for this language.';
            }
            if (meta?.filtered_out) {
                return 'Nothing passed the relevance threshold for this language.';
            }
            return 'No results found.';
        },

        async performSearch() {
            if (!this.searchQuery.trim()) {
                this.notify('Please enter a search query');
                return;
            }
            if (!this.selectedLanguages.length) {
                this.notify('Please select at least one language');
                return;
            }

            this.loading = true;
            this.clearNotice();
            try {
                const response = await fetch('/api/search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        query: this.searchQuery,
                        languages: this.selectedLanguages,
                        num_results: this.numResults,
                        filter_by_relevance: this.filterByRelevance,
                        search_custom_db: this.searchCustomDB
                    })
                });

                const data = await response.json().catch(() => ({}));
                if (!response.ok) {
                    this.notify('Search failed: ' + (data.detail || `HTTP ${response.status}`));
                    return;
                }
                if (data.success) {
                    this.searchResults = data.results;
                    this.searchMeta = data.meta || {};
                    // Activate the first language the user actually selected.
                    this.activeLang = this.selectedLanguages[0]
                        || Object.keys(data.results)[0]
                        || null;
                } else {
                    this.notify('Search failed');
                }
            } catch (error) {
                console.error('Search error:', error);
                this.notify('Error performing search: ' + error.message);
            } finally {
                this.loading = false;
            }
        },

        handleFileUpload(event) {
            this.uploadedFile = event.target.files[0];
        },

        async performOCR() {
            if (!this.uploadedFile) {
                this.notify('Please select a file');
                return;
            }

            this.loading = true;
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
            formData.append('language', this.ocrLanguage);

            try {
                const response = await fetch('/api/ocr', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();
                if (data.success) {
                    this.searchQuery = data.text.substring(0, 500);
                    this.notify('OCR completed! Text extracted and added to search box.', 'success');
                } else {
                    this.notify('OCR failed: ' + (data.error || 'unknown error'));
                }
            } catch (error) {
                console.error('OCR error:', error);
                this.notify('Error processing file: ' + error.message);
            } finally {
                this.loading = false;
            }
        },

        async addCustomSite() {
            if (!this.newSite.url || !this.newSite.title) {
                this.notify('Please fill in URL and Title');
                return;
            }

            try {
                const response = await fetch('/api/custom-sites/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(this.newSite)
                });

                const data = await response.json();
                if (data.success) {
                    this.newSite = { url: '', title: '', category: '', tags: '' };
                    this.loadCustomSites();
                    this.notify('Site added successfully', 'success');
                } else {
                    this.notify('Failed to add site');
                }
            } catch (error) {
                console.error('Add site error:', error);
                this.notify('Error adding site: ' + error.message);
            }
        },

        async loadCustomSites() {
            try {
                const response = await fetch('/api/custom-sites');
                const data = await response.json();
                if (data.success) {
                    this.customSites = data.sites;
                }
            } catch (error) {
                console.error('Load sites error:', error);
            }
        },

        async removeCustomSite(site) {
            if (!confirm('Are you sure you want to delete this site?')) {
                return;
            }

            try {
                const response = await fetch(`/api/custom-sites/${site.id}`, {
                    method: 'DELETE'
                });

                const data = await response.json();
                if (data.success) {
                    this.loadCustomSites();
                    this.notify('Site deleted', 'success');
                } else {
                    this.notify('Failed to delete site');
                }
            } catch (error) {
                console.error('Delete site error:', error);
                this.notify('Error deleting site: ' + error.message);
            }
        },

        async addToCustomDB(result) {
            try {
                const response = await fetch('/api/custom-sites/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        url: result.url,
                        title: result.title,
                        category: 'search_result',
                        tags: 'from_search'
                    })
                });

                const data = await response.json();
                if (data.success) {
                    this.loadCustomSites();
                    this.notify('Added to custom database', 'success');
                }
            } catch (error) {
                console.error('Add to DB error:', error);
                this.notify('Error adding to database: ' + error.message);
            }
        },

        async removeFromCustomDB(site) {
            if (!confirm('Remove from custom database?')) {
                return;
            }

            try {
                const response = await fetch(`/api/custom-sites/${site.id}`, {
                    method: 'DELETE'
                });

                const data = await response.json();
                if (data.success) {
                    this.loadCustomSites();
                    if (this.searchResults && this.searchResults.custom_db) {
                        this.searchResults.custom_db = this.searchResults.custom_db.filter(s => s.id !== site.id);
                    }
                }
            } catch (error) {
                console.error('Remove error:', error);
            }
        }
    }
}).mount('#app');
