import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/worlds/new', name: 'world-builder', component: () => import('@/views/WorldBuilderView.vue') },
    { path: '/play/:playthroughId', name: 'play', component: () => import('@/views/PlayView.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
    { path: '/inspector', name: 'inspector', component: () => import('@/views/InspectorView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})
