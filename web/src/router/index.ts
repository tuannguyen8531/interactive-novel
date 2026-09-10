import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    }
    return { top: 0 }
  },
  routes: [
    { path: '/', name: 'home', component: () => import('@/views/HomeView.vue') },
    { path: '/worlds/new', name: 'world-builder', component: () => import('@/views/WorldBuilderView.vue') },
    { path: '/play/:playthroughId', name: 'play', component: () => import('@/views/PlayView.vue') },
    { path: '/settings', name: 'settings', component: () => import('@/views/SettingsView.vue') },
    { path: '/data', redirect: '/settings' },
    { path: '/inspector', name: 'inspector', component: () => import('@/views/InspectorView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/' }
  ]
})
