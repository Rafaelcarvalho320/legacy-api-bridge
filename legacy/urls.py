from rest_framework.routers import DefaultRouter

from legacy.views import CityViewSet, ClientViewSet, OrderViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("orders", OrderViewSet, basename="order")
router.register("cities", CityViewSet, basename="city")

urlpatterns = router.urls
