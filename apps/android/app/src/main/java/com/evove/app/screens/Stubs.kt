package com.evove.app.screens

import androidx.compose.runtime.Composable

@Composable fun ShopScreen(onHome: () -> Unit) {}
@Composable fun BuildScreen(onHome: () -> Unit) {}
@Composable fun AgendaScreen(onHome: () -> Unit, onCalendar: () -> Unit, onLogs: () -> Unit) {}
@Composable fun JourneyScreen(onHome: () -> Unit) {}
@Composable fun RokoScreen(onHome: () -> Unit) {}
@Composable fun MeScreen(onHome: () -> Unit, onProfile: () -> Unit, onDetails: () -> Unit) {}
@Composable fun ProfilePage(onBack: () -> Unit, onLogout: (Boolean) -> Unit) {}
@Composable fun DetailsPage(onBack: () -> Unit) {}
@Composable fun CalendarPage(onBack: () -> Unit) {}
@Composable fun LogsPage(onBack: () -> Unit) {}
