from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect
from django.utils import timezone
from .forms import CheckoutForm, CouponForm, RefundForm
from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund

import random
import string
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            form = CheckoutForm()
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }
            shipping_address_qs = Address.objects.filter(
                user=self.request.user, address_type='S', default=True)
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})
            billing_address_qs = Address.objects.filter(
                user=self.request.user, address_type='B', default=True)
            if billing_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})

            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You Do Not Have an Active Order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():

                # SHIPPING ADDRESS SECTION BEGINS
                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    print("USE THE DEFAULT SHIPPING ADDRESS")
                    address_qs = Address.objects.filter(
                        user=self.request.user, address_type='S', default=True)
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No Default Shipping Address Available")
                        return redirect('core:checkout')
                else:
                    print("USER IS ENTERING A NEW SHIPPING ADDRESS")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address1')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(user=self.request.user, street_address=shipping_address1,
                                                   apartment_address=shipping_address2, country=shipping_country, zip=shipping_zip, address_type='S')
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            # Makes Old Default Shipping Address Not Default Anymore
                            old_default_address_qs = Address.objects.filter(
                                user=self.request.user, address_type='S', default=True)
                            if old_default_address_qs.exists():
                                old_default_shipping_address = old_default_address_qs[0]
                                old_default_shipping_address.default = False
                                old_default_shipping_address.save()
                            # Makes New Shipping Address Default
                            shipping_address.default = True
                            shipping_address.save()
                    else:
                        messages.info(
                            self.request, "Please Fill in the Required Shipping Address Fields")
                        return redirect('core:checkout')
                # SHIPPING ADDRESS SECTION ENDS

                # BILLING ADDRESS SECTION BEGINS
                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')
                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')

                # Billing Address Is Same as Shipping Address
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()
                # Uses Default Billing Address
                elif use_default_billing:
                    print("USE THE DEFAULT BILLING ADDRESS")
                    address_qs = Address.objects.filter(
                        user=self.request.user, address_type='B', default=True)
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No Default Billing Address Available")
                        return redirect('core:checkout')
                # User Enters in Billing Address
                else:
                    print("USER IS ENTERING A NEW BILLING ADDRESS")
                    billing_address1 = form.cleaned_data.get(
                        'billing_address1')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(user=self.request.user, street_address=billing_address1,
                                                  apartment_address=billing_address2, country=billing_country, zip=billing_zip, address_type='B')
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            # Makes Old Default Billing Address Not Default Anymore
                            old_default_address_qs = Address.objects.filter(
                                user=self.request.user, address_type='B', default=True)
                            if old_default_address_qs.exists():
                                old_default_billing_address = old_default_address_qs[0]
                                old_default_billing_address.default = False
                                old_default_billing_address.save()
                            # Makes New Billing Address Default
                            billing_address.default = True
                            billing_address.save()
                    else:
                        messages.info(
                            self.request, "Please Fill in the Required Billing Address Fields")
                        return redirect('core:checkout')
                # BILLING ADDRESS SECTION ENDS

            # PAYMENT SECTION BEGINS
            payment_option = form.cleaned_data.get('payment_option')

            if payment_option == 'S':
                return redirect('core:payment', payment_option='stripe')
            if payment_option == 'P':
                return redirect('core:payment', payment_option='paypal')
            else:
                messages.warning(
                    self.request, "Invalid Payment Option Selected")
                return redirect('core:checkout')
            # PAYMENT SECTION ENDS
        except ObjectDoesNotExist:
            messages.warning(self.request, "You Do Not Have an Active Order")
            return redirect("core:order-summary")


class PaymentView(View):
    def get(self, *args, **kwargs):
        # Order
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False
            }
            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "You Have Not Added a Billing Address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)  # Cents

        try:
            charge = stripe.Charge.create(
                amount=amount,
                currency="usd",
                source=token  # Obtained With Stripe.js
            )

            # Create the Payment
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # Mark All Order Items as Ordered
            for order_item in order.items.all():
                order_item.ordered = True
                order_item.save()

            # Assign the Payment to the Order
            order.ordered = True
            order.payment = payment
            order.ref_code = create_ref_code()
            order.save()

            messages.success(self.request, "Your Order Was Successful")
            return redirect("/")
        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body  # I Added This
            err = body.get('error', {})  # I Added This
            messages.warning(self.request, f"{err.get('message')}")
            return redirect("/")
        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.warning(self.request, "Rate Limit Error")
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.warning(self.request, "Invalid Parameters")
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.warning(self.request, "Not Authenticated")
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.warning(self.request, "Network Error")
            return redirect("/")
        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.warning(
                self.request, "Something went wrong. You were not charged. Please try again.")
            return redirect("/")
        except Exception as e:
            # Send an Email to Ourselves
            messages.warning(
                self.request, "A serious error occurred. We have been notified.")
            return redirect("/")


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = "home.html"


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You Do Not Have an Active Order")
            return redirect("/")


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # Check if the order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This Item Quantity Was Updated")
            return redirect("core:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "This Item Was Added to Your Cart")
            return redirect("core:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This Item Was Added to Your Cart")
        return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # Check if the order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            order.items.remove(order_item)
            messages.info(request, "This Item Was Removed From Your Cart")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This Item Was Not in Your Cart")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You Do Not Have an Active Order")
        return redirect("core:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # Check if the order item is in the order.
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
                messages.info(request, "This Item Quantity Was Updated")
                return redirect("core:order-summary")
            else:
                order.items.remove(order_item)
                messages.info(request, "This Item Was Removed From Your Cart")
                return redirect("core:order-summary")
        else:
            messages.info(request, "This Item Was Not in Your Cart")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You Do Not Have an Active Order")
        return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This Promo Code Does Not Exist")
        return redirect("core:checkout")


class AddCouponView(View):
    def get(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully Added Promo Code")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You Do Not Have an Active Order")
                return redirect("core:checkout")
            except Exception as e:
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # Edit the Order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()
                # Store the Refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()
                messages.info(self.request, "Your Request Was Received")
                return redirect("core:request-refund")
            except ObjectDoesNotExist:
                messages.info(self.request, "This Order Does Not Exist")
                return redirect("core:request-refund")
