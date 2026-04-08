const { createApp } = Vue;

createApp({
    data() {
        return {
            searchQuery: '',
            selectedLanguages: ['en', 'de', 'it'],
            numResults: 10,
            filterByRelevance: true,
            searchCustomDB: true,
            searchResults: null,
            loading: false,
            activeTab: 'English',
            customSites: [],
            uploadedFile: null,
            newSite: {
                url: '',
                title: '',
                category: '',
                tags: ''
            },
            tabs: ['English', 'Deutsch', 'Italiano', 'Custom DB']
        };
    },
    
    mounted() {
        this.loadCustomSites();
    },
    
    methods: {
        async performSearch() {
            if (!this.searchQuery.trim()) {
                alert('Please enter a search query');
                return;
            }
            
            this.loading = true;
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
                
                const data = await response.json();
                if (data.success) {
                    this.searchResults = data.results;
                    this.activeTab = 'English';
                } else {
                    alert('Search failed');
                }
            } catch (error) {
                console.error('Search error:', error);
                alert('Error performing search: ' + error.message);
            } finally {
                this.loading = false;
            }
        },
        
        handleFileUpload(event) {
            this.uploadedFile = event.target.files[0];
        },
        
        async performOCR() {
            if (!this.uploadedFile) {
                alert('Please select a file');
                return;
            }
            
            this.loading = true;
            const formData = new FormData();
            formData.append('file', this.uploadedFile);
            formData.append('language', 'eng');
            
            try {
                const response = await fetch('/api/ocr', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                if (data.success) {
                    this.searchQuery = data.text.substring(0, 500);
                    alert('OCR completed! Text extracted and added to search box.');
                } else {
                    alert('OCR failed: ' + data.error);
                }
            } catch (error) {
                console.error('OCR error:', error);
                alert('Error processing file: ' + error.message);
            } finally {
                this.loading = false;
            }
        },
        
        async addCustomSite() {
            if (!this.newSite.url || !this.newSite.title) {
                alert('Please fill in URL and Title');
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
                    alert('Site added successfully');
                } else {
                    alert('Failed to add site');
                }
            } catch (error) {
                console.error('Add site error:', error);
                alert('Error adding site: ' + error.message);
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
        
        async removeCustomSite(url) {
            if (!confirm('Are you sure you want to delete this site?')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/custom-sites/${encodeURIComponent(url)}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                if (data.success) {
                    this.loadCustomSites();
                    alert('Site deleted');
                } else {
                    alert('Failed to delete site');
                }
            } catch (error) {
                console.error('Delete site error:', error);
                alert('Error deleting site: ' + error.message);
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
                    alert('Added to custom database');
                }
            } catch (error) {
                console.error('Add to DB error:', error);
                alert('Error adding to database: ' + error.message);
            }
        },
        
        async removeFromCustomDB(url) {
            if (!confirm('Remove from custom database?')) {
                return;
            }
            
            try {
                const response = await fetch(`/api/custom-sites/${encodeURIComponent(url)}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                if (data.success) {
                    this.loadCustomSites();
                    if (this.searchResults && this.searchResults.custom_db) {
                        this.searchResults.custom_db = this.searchResults.custom_db.filter(s => s.url !== url);
                    }
                }
            } catch (error) {
                console.error('Remove error:', error);
            }
        }
    }
}).mount('#app');
